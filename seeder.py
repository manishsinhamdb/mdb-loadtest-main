"""Idempotent seeder. Runs before load against the chosen DB.

Creates the collections each workload class needs, with deterministic content
when a seed is supplied. Re-running tops up to the requested counts rather than
duplicating. Records exactly what it created/ensured for the manifest.
"""
from __future__ import annotations

import random

from pymongo import ASCENDING, MongoClient

import config


def _rand_payload(rng: random.Random, kb: int = 1) -> str:
    # ~kb*1024 chars of filler so docs have realistic size for cache pressure.
    return rng.choice("abcdefghijklmnopqrstuvwxyz") * (kb * 1024)


def _seed_large(db, count: int, rng: random.Random, log, batch: int = 5000) -> dict:
    coll = db[config.COLL_LARGE]
    existing = coll.estimated_document_count()
    # Indexed field user_id, unindexed field random_tag.
    coll.create_index([("user_id", ASCENDING)], name="user_id_idx")
    created = 0
    if existing < count:
        to_add = count - existing
        log.info(f"seeder: topping up '{config.COLL_LARGE}' by {to_add} docs (have {existing}, want {count})")
        buf = []
        for i in range(existing, count):
            buf.append({
                "user_id": rng.randint(1, max(1, count // 10)),
                "random_tag": rng.randint(1, config.TAG_CARDINALITY),  # UNINDEXED on purpose
                "value": rng.random(),
                "payload": _rand_payload(rng, 1),
            })
            if len(buf) >= batch:
                coll.insert_many(buf, ordered=False)
                created += len(buf)
                buf = []
        if buf:
            coll.insert_many(buf, ordered=False)
            created += len(buf)
    else:
        log.info(f"seeder: '{config.COLL_LARGE}' already has {existing} >= {count}; leaving as-is")
    return {
        "collection": config.COLL_LARGE,
        "count": coll.estimated_document_count(),
        "inserted": created,
        "indexes": ["user_id_idx (user_id)", "random_tag is intentionally UNINDEXED"],
    }


def _seed_agg(db, count: int, rng: random.Random, log, batch: int = 5000) -> dict:
    coll = db[config.COLL_AGG]
    coll.create_index([("category", ASCENDING)], name="category_idx")
    existing = coll.estimated_document_count()
    created = 0
    cats = [f"cat_{i}" for i in range(20)]
    if existing < count:
        to_add = count - existing
        log.info(f"seeder: topping up '{config.COLL_AGG}' by {to_add} docs")
        buf = []
        for i in range(existing, count):
            buf.append({
                "category": rng.choice(cats),
                "amount": round(rng.uniform(1, 1000), 2),
                "tags": [f"t{rng.randint(0, 9)}" for _ in range(rng.randint(1, 5))],
                "items": [{"sku": rng.randint(1, 500), "qty": rng.randint(1, 10)}
                          for _ in range(rng.randint(1, 6))],
                "ts": rng.randint(1_600_000_000, 1_700_000_000),
            })
            if len(buf) >= batch:
                coll.insert_many(buf, ordered=False)
                created += len(buf)
                buf = []
        if buf:
            coll.insert_many(buf, ordered=False)
            created += len(buf)
    return {
        "collection": config.COLL_AGG,
        "count": coll.estimated_document_count(),
        "inserted": created,
        "indexes": ["category_idx (category)"],
    }


def _seed_hot(db, hot_docs: int, rng: random.Random, log) -> dict:
    coll = db[config.COLL_HOT]
    existing = coll.estimated_document_count()
    created = 0
    if existing < hot_docs:
        docs = [{"_id": i, "counter": 0, "owner": None} for i in range(existing, hot_docs)]
        if docs:
            coll.insert_many(docs, ordered=False)
            created = len(docs)
    log.info(f"seeder: '{config.COLL_HOT}' has {coll.estimated_document_count()} hot docs")
    return {"collection": config.COLL_HOT, "count": coll.estimated_document_count(),
            "inserted": created, "indexes": ["_id (default)"]}


def _seed_append(db, log) -> dict:
    # write_bursts appends here; just ensure it exists.
    if config.COLL_APPEND not in db.list_collection_names():
        db.create_collection(config.COLL_APPEND)
    coll = db[config.COLL_APPEND]
    return {"collection": config.COLL_APPEND, "count": coll.estimated_document_count(),
            "inserted": 0, "indexes": ["_id (default)"]}


def seed(
    client: MongoClient,
    db_name: str,
    log,
    *,
    large_count: int = config.DEFAULT_SEED_LARGE_COUNT,
    agg_count: int = config.DEFAULT_SEED_AGG_COUNT,
    hot_docs: int = config.DEFAULT_HOT_DOCS,
    seed: int | None = None,
) -> dict:
    """Seed all collections idempotently; return a manifest-ready summary."""
    rng = random.Random(seed)
    db = client[db_name]
    log.info(f"seeder: starting on db='{db_name}' "
             f"(large={large_count}, agg={agg_count}, hot={hot_docs}, seed={seed})")
    summary = {
        "db": db_name,
        "params": {"large_count": large_count, "agg_count": agg_count,
                   "hot_docs": hot_docs, "seed": seed},
        "collections": [
            _seed_large(db, large_count, rng, log),
            _seed_agg(db, agg_count, rng, log),
            _seed_hot(db, hot_docs, rng, log),
            _seed_append(db, log),
        ],
    }
    log.info("seeder: complete")
    return summary


# Minimum counts a run requires before it will fire (seeder-not-run guard).
def is_seeded(client: MongoClient, db_name: str) -> tuple[bool, str]:
    db = client[db_name]
    names = set(db.list_collection_names())
    needed = {config.COLL_LARGE, config.COLL_AGG, config.COLL_HOT, config.COLL_APPEND}
    missing = needed - names
    if missing:
        return False, f"seeder not run — missing collections: {sorted(missing)}"
    if db[config.COLL_LARGE].estimated_document_count() == 0:
        return False, f"seeder not run — '{config.COLL_LARGE}' is empty"
    if db[config.COLL_HOT].estimated_document_count() == 0:
        return False, f"seeder not run — '{config.COLL_HOT}' is empty"
    return True, "seeded"
