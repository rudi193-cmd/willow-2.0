"""
willow/sigmap/__init__.py — SigMap: code signature indexer for Willow.
b17: SMAP1  ΔΣ=42

Port of SigMap (manojmallick/sigmap) logic into Willow's Python stack.
Extracts code signatures, classifies files by complexity tier, builds
dependency graphs, ranks context by TF-IDF, and writes to jeles_atoms.
"""

from willow.sigmap.extractor import extract, extract_file
from willow.sigmap.classifier import classify
from willow.sigmap.ranking import rank
from willow.sigmap.impact import get_impact
from willow.sigmap.graph import build_graph
from willow.sigmap.indexer import index_directory

__all__ = [
    "extract",
    "extract_file",
    "classify",
    "rank",
    "get_impact",
    "build_graph",
    "index_directory",
]
