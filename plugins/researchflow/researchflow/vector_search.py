from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .schema import project_dirs
from .store import init_project, load_experiments

DEFAULT_VECTOR_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_COLLECTION = "experiments"
VECTOR_INDEX_DIR = "chroma"
INSTALL_HINT = 'pip install "researchflow[vector]"'


class VectorSearchUnavailable(RuntimeError):
    pass


def _load_chromadb() -> Any:
    try:
        import chromadb  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on optional package
        raise VectorSearchUnavailable(f"ChromaDB is required for vector search. Install with: {INSTALL_HINT}") from exc
    return chromadb


def _load_sentence_transformer() -> Any:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on optional package
        raise VectorSearchUnavailable(
            f"sentence-transformers is required for local semantic embeddings. Install with: {INSTALL_HINT}"
        ) from exc
    return SentenceTransformer


def vector_store_path(root: Path) -> Path:
    return project_dirs(root)["indexes"] / VECTOR_INDEX_DIR


def _client(root: Path) -> Any:
    chromadb = _load_chromadb()
    return chromadb.PersistentClient(path=str(vector_store_path(root)))


def _model(model_name: str) -> Any:
    SentenceTransformer = _load_sentence_transformer()
    return SentenceTransformer(model_name)


def _collection(client: Any) -> Any:
    return client.get_or_create_collection(
        VECTOR_COLLECTION,
        metadata={"hnsw:space": "cosine", "description": "ResearchFlow experiment records"},
    )


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _text_list(title: str, values: Any, *, limit: int = 40) -> list[str]:
    values = _as_list(values)
    if not values:
        return []
    rendered = ", ".join(str(value) for value in values[:limit] if str(value).strip())
    return [f"{title}: {rendered}"] if rendered else []


def _text_mapping(title: str, values: Any, *, limit: int = 80) -> list[str]:
    if not isinstance(values, dict) or not values:
        return []
    items = []
    for key, value in sorted(values.items(), key=lambda item: str(item[0]))[:limit]:
        if isinstance(value, (dict, list)):
            continue
        if value is None or value == "":
            continue
        items.append(f"{key}={value}")
    return [f"{title}: " + ", ".join(items)] if items else []


def experiment_document(record: dict[str, Any]) -> str:
    lines = [
        f"Experiment ID: {record.get('id', '')}",
        f"Title: {record.get('title') or ''}",
        f"Version: {record.get('version') or ''}",
        f"Kind: {record.get('kind') or ''}",
        f"Status: {record.get('status') or ''}",
    ]
    lines.extend(_text_list("Tags", record.get("tags", [])))
    lines.extend(_text_list("Parents", record.get("parents", [])))
    lines.extend(_text_list("Merged from", record.get("merged_from", [])))
    lines.extend(_text_list("Cites", record.get("cites", [])))
    lines.extend(_text_list("Supersedes", record.get("supersedes", [])))
    lines.extend(_text_list("Improves", record.get("improves", [])))
    lines.extend(_text_list("Regresses", record.get("regresses", [])))
    lines.extend(_text_list("Claims", record.get("claims", [])))
    lines.extend(_text_mapping("Metrics", record.get("metrics", {})))
    lines.extend(_text_mapping("Params", record.get("params", {})))
    lines.extend(_text_list("Run paths", record.get("run_paths", [])))
    lines.extend(_text_list("Artifacts", record.get("artifacts", [])))
    if record.get("decision"):
        lines.append(f"Decision: {record.get('decision')}")
    if record.get("notes"):
        lines.append(f"Notes: {record.get('notes')}")
    lines.extend(_text_list("Next steps", record.get("next_steps", [])))
    return "\n".join(line for line in lines if line.strip())


def _metadata(record: dict[str, Any]) -> dict[str, str | int | float | bool]:
    metadata: dict[str, str | int | float | bool] = {}
    for key in ("id", "version", "title", "kind", "status", "updated_at"):
        value = record.get(key)
        if isinstance(value, (int, float, bool)):
            metadata[key] = value
        elif value is not None:
            metadata[key] = str(value)
    return metadata


def _as_embeddings(value: Any) -> list[list[float]]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    return [[float(item) for item in row] for row in value]


def _encode_documents(model: Any, documents: list[str], *, batch_size: int) -> list[list[float]]:
    encoder: Callable[..., Any] = getattr(model, "encode_document", None) or model.encode
    return _as_embeddings(encoder(documents, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False))


def _encode_query(model: Any, query: str) -> list[float]:
    encoder: Callable[..., Any] = getattr(model, "encode_query", None) or model.encode
    embeddings = _as_embeddings(encoder([query], normalize_embeddings=True, show_progress_bar=False))
    return embeddings[0]


def _delete_collection(client: Any) -> None:
    try:
        client.delete_collection(VECTOR_COLLECTION)
    except Exception:
        pass


def build_vector_index(
    root: Path,
    *,
    model_name: str = DEFAULT_VECTOR_MODEL,
    reset: bool = False,
    batch_size: int = 32,
    client: Any | None = None,
    model: Any | None = None,
) -> dict[str, Any]:
    init_project(root)
    experiments = load_experiments(root)
    client = client or _client(root)
    if reset:
        _delete_collection(client)
    collection = _collection(client)

    ids = [str(record["id"]) for record in experiments if record.get("id")]
    documents = [experiment_document(record) for record in experiments if record.get("id")]
    metadatas = [_metadata(record) for record in experiments if record.get("id")]

    existing = collection.get(include=[])
    stale_ids = sorted(set(existing.get("ids", [])) - set(ids))
    if stale_ids:
        collection.delete(ids=stale_ids)

    if documents:
        model = model or _model(model_name)
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=_encode_documents(model, documents, batch_size=batch_size),
        )

    return {
        "ok": True,
        "collection": VECTOR_COLLECTION,
        "documents": len(documents),
        "deleted": len(stale_ids),
        "model": model_name,
        "path": str(vector_store_path(root)),
    }


def vector_search_experiments(
    root: Path,
    query: str,
    *,
    limit: int = 10,
    model_name: str = DEFAULT_VECTOR_MODEL,
    client: Any | None = None,
    model: Any | None = None,
) -> list[dict[str, Any]]:
    if not query.strip():
        return []
    client = client or _client(root)
    collection = _collection(client)
    if collection.count() == 0:
        return []

    model = model or _model(model_name)
    result = collection.query(
        query_embeddings=[_encode_query(model, query)],
        n_results=limit,
        include=["documents", "metadatas", "distances"],
    )

    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    rows: list[dict[str, Any]] = []
    for index, exp_id in enumerate(ids):
        metadata = metadatas[index] if index < len(metadatas) else {}
        distance = distances[index] if index < len(distances) else None
        document = documents[index] if index < len(documents) else ""
        rows.append(
            {
                "id": exp_id,
                "version": metadata.get("version"),
                "title": metadata.get("title"),
                "status": metadata.get("status"),
                "kind": metadata.get("kind"),
                "score": None if distance is None else 1.0 - float(distance),
                "distance": distance,
                "snippet": str(document).splitlines()[0:6],
            }
        )
    return rows


def vector_index_status(root: Path, *, client: Any | None = None) -> dict[str, Any]:
    path = vector_store_path(root)
    status: dict[str, Any] = {"path": str(path), "exists": path.exists(), "collection": VECTOR_COLLECTION}
    if client is None and not path.exists():
        return status
    try:
        client = client or _client(root)
        status["documents"] = _collection(client).count()
        status["ok"] = True
    except VectorSearchUnavailable as exc:
        status["ok"] = False
        status["error"] = str(exc)
    except Exception as exc:
        status["ok"] = False
        status["error"] = str(exc)
    return status
