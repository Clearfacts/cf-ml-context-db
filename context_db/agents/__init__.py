"""
context_db.agents — agent entry points built on top of the context database.
"""

__all__ = ["SourceOntologyQueryAgent", "ClearfactsNavigationAgent", "ClearfactsNavigationDeepAgent"]


def __getattr__(name: str):
    if name == "ClearfactsNavigationAgent":
        from .clearfacts_navigation_agent import ClearfactsNavigationAgent

        return ClearfactsNavigationAgent
    if name == "ClearfactsNavigationDeepAgent":
        from .clearfacts_navigation_deepagent import ClearfactsNavigationDeepAgent

        return ClearfactsNavigationDeepAgent
    if name == "SourceOntologyQueryAgent":
        from .source_ontology_query_agent import SourceOntologyQueryAgent

        return SourceOntologyQueryAgent
    raise AttributeError(name)
