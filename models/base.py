"""
Capa de Repositorio Documental para PostgreSQL (JSONB).

Ejecuta operaciones asíncronas directas contra PostgreSQL usando asyncpg,
con tablas tipadas y restricciones de integridad en el esquema `xuve`.
"""

from decimal import Decimal

from db.pg import get_pool
from db.schema import COLLECTIONS

_KNOWN = set(COLLECTIONS)
_ensured: set[str] = set()

_COMPARATORS = {"$gt": ">", "$gte": ">=", "$lt": "<", "$lte": "<="}

# Campos escalares "calientes" (con índice B-Tree dedicado): la igualdad usa SOLO
# la comparación escalar indexada (rápida). El resto de campos string usan además
# la regla de "el array contiene el valor" (containment @>), porque en
# {campo: valor} matchea tanto igualdad escalar como pertenencia a un array.
_SCALAR_FIELDS = {
    "user_id", "email", "session_token", "conversation_id", "store_id",
    "product_id", "hold_id", "transaction_id", "order_id", "service_id",
    "rate_id", "status", "type", "role", "kyc_status", "sub_role",
}


# ---------------------------------------------------------------------------
# Objetos de resultado de operaciones PostgreSQL
# ---------------------------------------------------------------------------
class InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id
        self.acknowledged = True


class InsertManyResult:
    def __init__(self, inserted_ids):
        self.inserted_ids = inserted_ids
        self.acknowledged = True


class UpdateResult:
    def __init__(self, matched_count, modified_count, upserted_id=None):
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.upserted_id = upserted_id
        self.acknowledged = True


class DeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count
        self.acknowledged = True


# ---------------------------------------------------------------------------
# Acumulador de parámetros posicionales ($1, $2, ...)
# ---------------------------------------------------------------------------
class _Params:
    def __init__(self):
        self.values = []

    def add(self, value) -> str:
        self.values.append(value)
        return f"${len(self.values)}"


# ---------------------------------------------------------------------------
# Expresiones de acceso a campos JSONB (clave parametrizada)
# ---------------------------------------------------------------------------
def _ftext(field: str, p: _Params) -> str:
    """Valor TEXTO del campo: (doc ->> 'k') o (doc #>> '{a,b}')."""
    parts = field.split(".")
    if len(parts) == 1:
        return f"(doc ->> {p.add(parts[0])})"
    return f"(doc #>> {p.add(parts)})"


def _fjson(field: str, p: _Params) -> str:
    """Valor JSONB del campo: (doc -> 'k') o (doc #> '{a,b}')."""
    parts = field.split(".")
    if len(parts) == 1:
        return f"(doc -> {p.add(parts[0])})"
    return f"(doc #> {p.add(parts)})"


def _path(field: str) -> list[str]:
    return field.split(".")


# ---------------------------------------------------------------------------
# Traducción de FILTROS JSONB -> SQL
# ---------------------------------------------------------------------------
def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _eq(field: str, val, p: _Params) -> str:
    if val is None:
        # {f: None} -> faltante o null. (->> de json-null devuelve NULL también.)
        return f"({_ftext(field, p)} IS NULL)"
    if isinstance(val, bool):
        return f"{_ftext(field, p)} = {p.add('true' if val else 'false')}"
    if isinstance(val, str):
        eq = f"{_ftext(field, p)} = {p.add(val)}"
        if field in _SCALAR_FIELDS:
            return eq
        # Igualdad escalar O pertenencia a array (containment).
        return f"({eq} OR {_fjson(field, p)} @> {p.add(val)})"
    if _is_num(val):
        return f"({_ftext(field, p)})::numeric = {p.add(val)}"
    # dict / list -> igualdad estructural jsonb
    return f"{_fjson(field, p)} = {p.add(val)}"


def _compare(field: str, op: str, operand, p: _Params) -> str:
    sqlop = _COMPARATORS[op]
    if _is_num(operand):
        return f"({_ftext(field, p)})::numeric {sqlop} {p.add(operand)}"
    return f"{_ftext(field, p)} {sqlop} {p.add(operand)}"


def _in(field: str, operand, p: _Params, negate: bool) -> str:
    operand = list(operand)
    acc = _ftext(field, p) if all(isinstance(x, str) for x in operand) else _fjson(field, p)
    expr = f"{acc} = ANY({p.add(operand)})"
    if negate:
        # $nin: también matchea documentos SIN el campo (NULL),
        # porque NOT(NULL) es NULL en SQL y excluiría esas filas indebidamente.
        return f"(NOT ({expr}) OR {acc} IS NULL)"
    return f"({expr})"


def _ne(field: str, operand, p: _Params) -> str:
    # $ne también matchea documentos sin el campo.
    if isinstance(operand, str) or operand is None:
        return f"({_ftext(field, p)} IS DISTINCT FROM {p.add(operand)})"
    if _is_num(operand):
        return f"({_ftext(field, p)})::numeric IS DISTINCT FROM {p.add(operand)}"
    return f"({_fjson(field, p)} IS DISTINCT FROM {p.add(operand)})"


def _exists(field: str, operand, p: _Params) -> str:
    present = f"(doc ? {p.add(field)})"
    return present if operand else f"(NOT {present})"


def _regex(field: str, pattern, options, p: _Params) -> str:
    opr = "~*" if options and "i" in options else "~"
    return f"{_ftext(field, p)} {opr} {p.add(pattern)}"


def _field_clause(field: str, val, p: _Params) -> str:
    if isinstance(val, dict) and any(k.startswith("$") for k in val):
        parts = []
        options = val.get("$options", "")
        for op, operand in val.items():
            if op in _COMPARATORS:
                parts.append(_compare(field, op, operand, p))
            elif op == "$in":
                parts.append(_in(field, operand, p, negate=False))
            elif op == "$nin":
                parts.append(_in(field, operand, p, negate=True))
            elif op == "$ne":
                parts.append(_ne(field, operand, p))
            elif op == "$exists":
                parts.append(_exists(field, operand, p))
            elif op == "$regex":
                parts.append(_regex(field, operand, options, p))
            elif op == "$options":
                continue
            else:
                raise NotImplementedError(f"Operador de filtro no soportado: {op}")
        return "(" + " AND ".join(parts) + ")" if parts else "TRUE"
    return _eq(field, val, p)


def _build_where(filt: dict, p: _Params) -> str:
    if not filt:
        return "TRUE"
    clauses = []
    for key, val in filt.items():
        if key == "$or":
            subs = [_build_where(s, p) for s in val]
            clauses.append("(" + " OR ".join(subs) + ")" if subs else "FALSE")
        elif key == "$and":
            subs = [_build_where(s, p) for s in val]
            clauses.append("(" + " AND ".join(subs) + ")" if subs else "TRUE")
        elif key == "$nor":
            subs = [_build_where(s, p) for s in val]
            clauses.append("(NOT (" + " OR ".join(subs) + "))" if subs else "TRUE")
        else:
            clauses.append(_field_clause(key, val, p))
    return " AND ".join(clauses) if clauses else "TRUE"


# ---------------------------------------------------------------------------
# Traducción de UPDATES JSONB -> expresión SQL para la columna `doc`
# ---------------------------------------------------------------------------
def _apply_update(update: dict, p: _Params) -> str:
    """Devuelve la expresión SQL que produce el nuevo `doc` a partir del actual."""
    if update and not any(k.startswith("$") for k in update):
        # Reemplazo total del documento.
        return p.add(update)

    expr = "doc"
    for op, fields in update.items():
        if op == "$set":
            for f, v in fields.items():
                expr = f"jsonb_set({expr}, {p.add(_path(f))}, {p.add(v)}, true)"
        elif op == "$unset":
            for f in fields:
                expr = f"({expr} #- {p.add(_path(f))})"
        elif op == "$inc":
            for f, delta in fields.items():
                pp = p.add(_path(f))
                expr = (
                    f"jsonb_set({expr}, {pp}, "
                    f"to_jsonb(COALESCE((doc #>> {pp})::numeric, 0) + {p.add(delta)}), true)"
                )
        elif op == "$min":
            for f, v in fields.items():
                pp = p.add(_path(f))
                vp = p.add(v)
                expr = (
                    f"jsonb_set({expr}, {pp}, "
                    f"to_jsonb(LEAST(COALESCE((doc #>> {pp})::numeric, {vp}), {vp})), true)"
                )
        elif op == "$max":
            for f, v in fields.items():
                pp = p.add(_path(f))
                vp = p.add(v)
                expr = (
                    f"jsonb_set({expr}, {pp}, "
                    f"to_jsonb(GREATEST(COALESCE((doc #>> {pp})::numeric, {vp}), {vp})), true)"
                )
        elif op == "$push":
            for f, v in fields.items():
                pp = p.add(_path(f))
                if isinstance(v, dict) and "$each" in v:
                    arr = list(v["$each"])
                else:
                    arr = [v]
                expr = (
                    f"jsonb_set({expr}, {pp}, "
                    f"COALESCE(doc #> {pp}, '[]'::jsonb) || {p.add(arr)}, true)"
                )
        elif op == "$pull":
            for f, cond in fields.items():
                pp = p.add(_path(f))
                expr = (
                    f"jsonb_set({expr}, {pp}, "
                    f"COALESCE((SELECT jsonb_agg(e) FROM jsonb_array_elements(doc #> {pp}) e "
                    f"WHERE e <> {p.add(cond)}), '[]'::jsonb), true)"
                )
        else:
            raise NotImplementedError(f"Operador de update no soportado: {op}")
    return expr


def _doc_from_filter(filt: dict) -> dict:
    """Para upsert: documento base con los pares de igualdad del filtro."""
    base = {}
    for k, v in filt.items():
        if k.startswith("$"):
            continue
        if isinstance(v, dict) and any(kk.startswith("$") for kk in v):
            continue
        base[k] = v
    return base


def _apply_update_py(base: dict, update: dict) -> dict:
    """Aplica el update en Python (solo para construir el doc de un upsert-insert)."""
    if update and not any(k.startswith("$") for k in update):
        return dict(update)
    d = dict(base)
    for op, fields in update.items():
        if op == "$set":
            d.update(fields)
        elif op == "$unset":
            for f in fields:
                d.pop(f, None)
        elif op == "$inc":
            for f, delta in fields.items():
                d[f] = (d.get(f) or 0) + delta
        elif op == "$min":
            for f, v in fields.items():
                d[f] = min(d[f], v) if f in d and d[f] is not None else v
        elif op == "$max":
            for f, v in fields.items():
                d[f] = max(d[f], v) if f in d and d[f] is not None else v
        elif op == "$push":
            for f, v in fields.items():
                arr = list(d.get(f) or [])
                arr.extend(v["$each"]) if isinstance(v, dict) and "$each" in v else arr.append(v)
                d[f] = arr
        elif op == "$pull":
            for f, cond in fields.items():
                d[f] = [e for e in (d.get(f) or []) if e != cond]
    return d


# ---------------------------------------------------------------------------
# Proyección (inclusión / exclusión de campos) — relevante p/ seguridad
# ---------------------------------------------------------------------------
def _project(doc, projection):
    if not doc or not projection:
        return doc
    incl = {k: v for k, v in projection.items() if k != "_id"}
    if not incl:
        return doc
    include_mode = any(v for v in incl.values())
    if include_mode:
        keep = {k for k, v in incl.items() if v}
        return {k: v for k, v in doc.items() if k in keep}
    drop = {k for k, v in incl.items() if not v}
    return {k: v for k, v in doc.items() if k not in drop}


def _order_sql(sort, p: _Params) -> str:
    if not sort:
        return ""
    if isinstance(sort, str):
        sort = [(sort, 1)]
    pieces = []
    for field, direction in sort:
        d = "DESC" if direction in (-1, "desc", "DESC") else "ASC"
        pieces.append(f"{_ftext(field, p)} {d}")
    return " ORDER BY " + ", ".join(pieces)


def _decimals_to_float(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


# ---------------------------------------------------------------------------
# Cursor para find()
# ---------------------------------------------------------------------------
class Cursor:
    def __init__(self, collection: "Collection", filt: dict, projection):
        self._c = collection
        self._filter = filt or {}
        self._projection = projection
        self._sort = None
        self._skip = 0
        self._limit = None

    def sort(self, key_or_list, direction=None):
        if isinstance(key_or_list, str):
            self._sort = [(key_or_list, direction if direction is not None else 1)]
        else:
            self._sort = list(key_or_list)
        return self

    def skip(self, n):
        self._skip = int(n)
        return self

    def limit(self, n):
        self._limit = int(n)
        return self

    async def to_list(self, length=None):
        p = _Params()
        where = _build_where(self._filter, p)
        sql = f"SELECT doc FROM {self._c._t} WHERE {where}"
        sql += _order_sql(self._sort, p)
        effective = self._limit
        if length is not None:
            effective = length if effective is None else min(effective, length)
        if effective is not None:
            sql += f" LIMIT {int(effective)}"
        if self._skip:
            sql += f" OFFSET {int(self._skip)}"
        pool = get_pool()
        async with pool.acquire() as conn:
            await self._c._ensure(conn)
            rows = await conn.fetch(sql, *p.values)
        return [_project(r["doc"], self._projection) for r in rows]


# ---------------------------------------------------------------------------
# Cursor para aggregate()
# ---------------------------------------------------------------------------
def _minmax_sql(field: str, desc: bool, p: _Params) -> str:
    """min/max robusto para campos numéricos O strings ISO, en una sola expresión."""
    kph = p.add(field)  # campos de min/max son de nivel superior en Xuve
    je = f"(doc -> {kph})"
    te = f"(doc ->> {kph})"
    direction = "DESC" if desc else "ASC"
    return (
        f"(array_agg({je} ORDER BY "
        f"CASE WHEN jsonb_typeof({je}) = 'number' THEN ({te})::numeric ELSE NULL END "
        f"{direction} NULLS LAST, {te} {direction}))[1]"
    )


def _accum_sql(acc: dict, p: _Params) -> str:
    (op, arg), = acc.items()
    if op == "$sum":
        if _is_num(arg):
            return "COUNT(*)" if arg == 1 else f"(COUNT(*) * {arg})"
        if isinstance(arg, str):
            return f"COALESCE(SUM(({_ftext(arg[1:], p)})::numeric), 0)"
        if isinstance(arg, dict) and "$abs" in arg:
            f = arg["$abs"][1:]
            return f"COALESCE(SUM(ABS(({_ftext(f, p)})::numeric)), 0)"
        raise NotImplementedError(f"$sum no soportado: {arg!r}")
    if op == "$avg":
        return f"AVG(({_ftext(arg[1:], p)})::numeric)"
    if op == "$min":
        return _minmax_sql(arg[1:], desc=False, p=p)
    if op == "$max":
        return _minmax_sql(arg[1:], desc=True, p=p)
    if op == "$count":
        return "COUNT(*)"
    raise NotImplementedError(f"Acumulador no soportado: {op}")


class AggregateCursor:
    def __init__(self, collection: "Collection", pipeline: list):
        self._c = collection
        self._pipeline = pipeline

    async def to_list(self, length=None):
        p = _Params()
        where = "TRUE"
        group_spec = None
        sort_spec = None
        limit = None
        for stage in self._pipeline:
            if "$match" in stage:
                where = _build_where(stage["$match"], p)
            elif "$group" in stage:
                group_spec = stage["$group"]
            elif "$sort" in stage:
                sort_spec = stage["$sort"]
            elif "$limit" in stage:
                limit = stage["$limit"]
            elif "$skip" in stage:
                pass
            else:
                raise NotImplementedError(f"Etapa de aggregate no soportada: {stage}")

        if length is not None:
            limit = length if limit is None else min(limit, length)

        # Sin $group: passthrough de documentos.
        if group_spec is None:
            sql = f"SELECT doc FROM {self._c._t} WHERE {where}"
            sql += _order_sql(_sort_dict_to_list(sort_spec), p) if sort_spec else ""
            if limit is not None:
                sql += f" LIMIT {int(limit)}"
            pool = get_pool()
            async with pool.acquire() as conn:
                await self._c._ensure(conn)
                rows = await conn.fetch(sql, *p.values)
            return [r["doc"] for r in rows]

        # Con $group:
        id_spec = group_spec["_id"]
        group_fields = []  # lista de (outkey|None, field)
        if id_spec is None:
            pass
        elif isinstance(id_spec, str):
            group_fields = [(None, id_spec[1:])]
        elif isinstance(id_spec, dict):
            group_fields = [(k, v[1:]) for k, v in id_spec.items()]
        else:
            raise NotImplementedError(f"_id de $group no soportado: {id_spec!r}")

        accums = [(name, spec) for name, spec in group_spec.items() if name != "_id"]

        selects, group_exprs = [], []
        for i, (_, field) in enumerate(group_fields):
            e = _fjson(field, p)
            selects.append(f"{e} AS g{i}")
            group_exprs.append(e)
        accum_names = []
        for name, spec in accums:
            selects.append(f'{_accum_sql(spec, p)} AS "{name}"')
            accum_names.append(name)

        sql = f"SELECT {', '.join(selects)} FROM {self._c._t} WHERE {where}"
        if group_exprs:
            sql += " GROUP BY " + ", ".join(group_exprs)
        else:
            sql += " HAVING COUNT(*) > 0"  # _id:None -> 1 fila solo si hay docs

        if sort_spec:
            pieces = []
            for k, d in sort_spec.items():
                direction = "DESC" if d == -1 else "ASC"
                if k == "_id" and len(group_fields) == 1:
                    pieces.append(f"g0 {direction}")
                else:
                    pieces.append(f'"{k}" {direction}')
            sql += " ORDER BY " + ", ".join(pieces)
        if limit is not None:
            sql += f" LIMIT {int(limit)}"

        pool = get_pool()
        async with pool.acquire() as conn:
            await self._c._ensure(conn)
            rows = await conn.fetch(sql, *p.values)

        out = []
        for r in rows:
            d = {}
            if not group_fields:
                d["_id"] = None
            elif group_fields[0][0] is None:
                d["_id"] = _decimals_to_float(r["g0"])
            else:
                d["_id"] = {
                    outk: _decimals_to_float(r[f"g{i}"])
                    for i, (outk, _) in enumerate(group_fields)
                }
            for name in accum_names:
                d[name] = _decimals_to_float(r[name])
            out.append(d)
        return out


def _sort_dict_to_list(sort_spec):
    if not sort_spec:
        return None
    return [(k, v) for k, v in sort_spec.items()]


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------
class Collection:
    def __init__(self, name: str):
        self.name = name
        self._t = f"xuve.{name}"

    async def _ensure(self, conn):
        """Crea la tabla on-the-fly si la colección no estaba en el bootstrap."""
        if self.name in _KNOWN or self.name in _ensured:
            return
        await conn.execute(
            f"CREATE TABLE IF NOT EXISTS {self._t} "
            "(pk BIGSERIAL PRIMARY KEY, doc JSONB NOT NULL, "
            "created_at timestamptz NOT NULL DEFAULT now())"
        )
        _ensured.add(self.name)

    # ---- lecturas --------------------------------------------------------
    async def find_one(self, filt=None, projection=None, sort=None):
        p = _Params()
        where = _build_where(filt or {}, p)
        sql = f"SELECT doc FROM {self._t} WHERE {where}"
        sql += _order_sql(sort, p)
        sql += " LIMIT 1"
        pool = get_pool()
        async with pool.acquire() as conn:
            await self._ensure(conn)
            row = await conn.fetchrow(sql, *p.values)
        return _project(row["doc"], projection) if row else None

    def find(self, filt=None, projection=None):
        return Cursor(self, filt or {}, projection)

    async def count_documents(self, filt=None):
        p = _Params()
        where = _build_where(filt or {}, p)
        sql = f"SELECT COUNT(*) FROM {self._t} WHERE {where}"
        pool = get_pool()
        async with pool.acquire() as conn:
            await self._ensure(conn)
            return int(await conn.fetchval(sql, *p.values))

    def aggregate(self, pipeline):
        return AggregateCursor(self, pipeline)

    # ---- escrituras ------------------------------------------------------
    async def insert_one(self, document):
        sql = f"INSERT INTO {self._t} (doc) VALUES ($1) RETURNING pk"
        pool = get_pool()
        async with pool.acquire() as conn:
            await self._ensure(conn)
            pk = await conn.fetchval(sql, document)
        return InsertOneResult(pk)

    async def insert_many(self, documents):
        docs = list(documents)
        sql = f"INSERT INTO {self._t} (doc) VALUES ($1) RETURNING pk"
        pool = get_pool()
        ids = []
        async with pool.acquire() as conn:
            await self._ensure(conn)
            async with conn.transaction():
                for d in docs:
                    ids.append(await conn.fetchval(sql, d))
        return InsertManyResult(ids)

    async def _update(self, filt, update, upsert, many):
        p = _Params()
        where = _build_where(filt or {}, p)
        new_doc_expr = _apply_update(update, p)
        if many:
            sql = f"UPDATE {self._t} SET doc = {new_doc_expr} WHERE {where}"
        else:
            sql = (
                f"UPDATE {self._t} SET doc = {new_doc_expr} "
                f"WHERE pk = (SELECT pk FROM {self._t} WHERE {where} LIMIT 1)"
            )
        pool = get_pool()
        async with pool.acquire() as conn:
            await self._ensure(conn)
            async with conn.transaction():
                status = await conn.execute(sql, *p.values)
                count = int(status.split()[-1])
                upserted = None
                if count == 0 and upsert:
                    new_doc = _apply_update_py(_doc_from_filter(filt or {}), update)
                    upserted = await conn.fetchval(
                        f"INSERT INTO {self._t} (doc) VALUES ($1) RETURNING pk", new_doc
                    )
        return UpdateResult(matched_count=count, modified_count=count, upserted_id=upserted)

    async def update_one(self, filt, update, upsert=False):
        return await self._update(filt, update, upsert, many=False)

    async def update_many(self, filt, update, upsert=False):
        return await self._update(filt, update, upsert, many=True)

    async def _delete(self, filt, many):
        p = _Params()
        where = _build_where(filt or {}, p)
        if many:
            sql = f"DELETE FROM {self._t} WHERE {where}"
        else:
            sql = (
                f"DELETE FROM {self._t} "
                f"WHERE pk = (SELECT pk FROM {self._t} WHERE {where} LIMIT 1)"
            )
        pool = get_pool()
        async with pool.acquire() as conn:
            await self._ensure(conn)
            status = await conn.execute(sql, *p.values)
        return DeleteResult(int(status.split()[-1]))

    async def delete_one(self, filt):
        return await self._delete(filt, many=False)

    async def delete_many(self, filt):
        return await self._delete(filt, many=True)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
class Database:
    def __init__(self):
        self._collections: dict[str, Collection] = {}

    def _get(self, name: str) -> Collection:
        col = self._collections.get(name)
        if col is None:
            col = Collection(name)
            self._collections[name] = col
        return col

    def __getattr__(self, name: str) -> Collection:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._get(name)

    def __getitem__(self, name: str) -> Collection:
        return self._get(name)


# Alias de clases para interoperabilidad
PostgresDatabase = Database
PostgresCollection = Collection


# ---------------------------------------------------------------------------
# Instancia global de acceso a tablas SQL para los Modelos
# ---------------------------------------------------------------------------
db = Database()


# ---------------------------------------------------------------------------
# Clase Base de Modelo SQL (Active Record / Consultas SQL en el Modelo)
# ---------------------------------------------------------------------------
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T", bound="PostgresBaseModel")


class PostgresBaseModel(BaseModel):
    """
    Modelo base de dominio con consultas SQL directas hacia PostgreSQL (esquema xuve).
    Todas las entidades del sistema heredan de esta clase para ejecutar SELECT,
    INSERT, UPDATE, DELETE y COUNT directamente desde el Modelo.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @classmethod
    def collection_name(cls) -> str:
        raw = getattr(cls, "_table_name", None)
        if raw is not None and hasattr(raw, "default"):
            raw = raw.default
        return raw if isinstance(raw, str) else (cls.__name__.lower() + "s")

    @classmethod
    def table(cls) -> Collection:
        return getattr(db, cls.collection_name())

    # ---- Consultas SQL explícitas en el Modelo ----------------------------

    @classmethod
    async def sql_fetch_one(cls, sql: str, *args) -> Optional[dict]:
        """Ejecuta un SELECT SQL directo y devuelve un registro."""
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(sql, *args)
            if not row:
                return None
            return row["doc"] if "doc" in row else dict(row)

    @classmethod
    async def sql_fetch_all(cls, sql: str, *args) -> List[dict]:
        """Ejecuta un SELECT SQL directo y devuelve múltiples registros."""
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
            return [r["doc"] if "doc" in r else dict(r) for r in rows]

    @classmethod
    async def sql_execute(cls, sql: str, *args) -> str:
        """Ejecuta una sentencia SQL (INSERT/UPDATE/DELETE) directa."""
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(sql, *args)

    @classmethod
    async def find_one(cls, filt: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None, sort=None) -> Optional[Dict[str, Any]]:
        """SELECT doc FROM xuve.<tabla> WHERE ... LIMIT 1"""
        return await cls.table().find_one(filt, projection, sort=sort)

    @classmethod
    def find(cls, filt: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None):
        """SELECT doc FROM xuve.<tabla> WHERE ..."""
        return cls.table().find(filt, projection)

    @classmethod
    async def find_many(cls, filt: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None, sort=None, limit: int = 100) -> List[Dict[str, Any]]:
        """SELECT doc FROM xuve.<tabla> WHERE ... ORDER BY ... LIMIT N"""
        cursor = cls.table().find(filt, projection)
        if sort:
            cursor = cursor.sort(sort)
        if limit:
            cursor = cursor.limit(limit)
        return await cursor.to_list(limit)

    @classmethod
    async def insert_one(cls, document: Dict[str, Any]):
        """INSERT INTO xuve.<tabla> (doc) VALUES ($1) RETURNING pk"""
        return await cls.table().insert_one(document)

    @classmethod
    async def insert_many(cls, documents: List[Dict[str, Any]]):
        """INSERT INTO xuve.<tabla> (doc) VALUES ($1) (múltiples)"""
        return await cls.table().insert_many(documents)

    @classmethod
    async def update_one(cls, filt: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        """UPDATE xuve.<tabla> SET doc = ... WHERE ... LIMIT 1"""
        return await cls.table().update_one(filt, update, upsert=upsert)

    @classmethod
    async def update_many(cls, filt: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        """UPDATE xuve.<tabla> SET doc = ... WHERE ..."""
        return await cls.table().update_many(filt, update, upsert=upsert)

    @classmethod
    async def delete_one(cls, filt: Dict[str, Any]):
        """DELETE FROM xuve.<tabla> WHERE ... LIMIT 1"""
        return await cls.table().delete_one(filt)

    @classmethod
    async def delete_many(cls, filt: Dict[str, Any]):
        """DELETE FROM xuve.<tabla> WHERE ..."""
        return await cls.table().delete_many(filt)

    @classmethod
    async def count_documents(cls, filt: Optional[Dict[str, Any]] = None) -> int:
        """SELECT COUNT(*) FROM xuve.<tabla> WHERE ..."""
        return await cls.table().count_documents(filt)

    @classmethod
    def aggregate(cls, pipeline: List[Dict[str, Any]]):
        """Agregación SQL sobre xuve.<tabla>"""
        return cls.table().aggregate(pipeline)

    # Alias cortos
    insert = insert_one
    update = update_one
    delete = delete_one
    count = count_documents
