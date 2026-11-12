"""Um módulo por fonte. Cada um expõe `buscar(cliente, slug) -> list[dict]` com as vagas brutas."""
from . import ashby, greenhouse, lever

COLETORES = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
}
