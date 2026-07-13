"""Public exception hierarchy for Membrane Visual QC."""


class MVQCError(Exception):
    """Base class for user-facing Membrane Visual QC errors."""


class InputValidationError(MVQCError, ValueError):
    """Raised when analysis input or parameters are invalid."""


class StructureParseError(MVQCError):
    """Raised when structure data cannot be parsed."""


class OrientationError(MVQCError):
    """Raised when membrane-orientation data are invalid."""


class ExternalServiceError(MVQCError):
    """Raised when an explicit external-service operation fails."""


class OptionalDependencyError(MVQCError):
    """Raised when a requested optional capability is unavailable."""


class ReportError(MVQCError):
    """Raised when a report is invalid or cannot be written."""


class PyMOLAdapterError(MVQCError):
    """Raised when a PyMOL-specific operation fails."""
