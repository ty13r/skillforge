"""Typed exception hierarchy for the skillforge package.

Every domain error inherits from ``SkldError`` so boundary handlers can
catch the whole family with one ``except`` clause while inner code can
still raise (and catch) precise types. See ``docs/clean-code.md`` §4.
"""

from __future__ import annotations


class SkldError(Exception):
    """Base class for every skillforge domain error."""


# --- Agent pipeline ---------------------------------------------------------


class AgentError(SkldError):
    """A failure inside an agent role (spawner, breeder, etc.)."""


class SpawnError(AgentError):
    """Spawner could not produce a valid initial variant population."""


class BreedError(AgentError):
    """Breeder could not evolve a next generation."""


class JudgeError(AgentError):
    """A judging layer (L1-L5) failed to produce a verdict."""


class EngineerError(AgentError):
    """Engineer failed to assemble or refine a composite skill."""


class TaxonomistError(AgentError):
    """Taxonomist failed to classify a specialization."""


class ChallengeDesignError(AgentError):
    """Challenge designer could not produce a valid challenge."""


# --- External integrations --------------------------------------------------


class AgentSDKError(SkldError):
    """The Anthropic / claude-agent SDK returned or raised unexpectedly.

    Distinct from ``AgentError`` — ``AgentSDKError`` is a *transport*
    failure (bad creds, rate limit, network), ``AgentError`` is a
    *semantic* failure (agent produced garbage output).
    """


class ManagedEnvironmentError(SkldError):
    """A hosted Managed-Agents environment could not be created, reused, or torn down."""


# --- Data + parsing ---------------------------------------------------------


class ParseError(SkldError, ValueError):
    """Could not parse a structured response (JSON, YAML, frontmatter, etc.).

    Inherits from ``ValueError`` so ``except ValueError`` continues to match
    parse failures in legacy call sites; new code should catch ``ParseError``
    to distinguish parse failures from other value errors.
    """


class ValidationError(SkldError, ValueError):
    """A parsed value violated a domain invariant."""


# --- Persistence ------------------------------------------------------------


class DBError(SkldError):
    """Database operation failed in an unexpected way.

    Catching this is always optional — most call sites should let it
    propagate so FastAPI's error middleware returns 500 with context.
    """


class StorageError(SkldError):
    """Filesystem / blob-storage operation failed (export, upload, etc.)."""
