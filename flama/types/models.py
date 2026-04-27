import typing as t

__all__ = ["Lib", "MLLib", "LLMLib", "is_ml_lib", "is_llm_lib"]

MLLib = t.Literal["sklearn", "tensorflow", "torch", "keras", "transformers"]
LLMLib = t.Literal["vllm"]
Lib = MLLib | LLMLib

_ML_LIBS: t.Final[tuple[MLLib, ...]] = t.get_args(MLLib)
_LLM_LIBS: t.Final[tuple[LLMLib, ...]] = t.get_args(LLMLib)


def is_ml_lib(lib: Lib) -> t.TypeGuard[MLLib]:
    """Check whether *lib* is a traditional ML framework.

    :param lib: Framework lib identifier.
    :return: ``True`` if *lib* is one of :data:`MLLib`, narrowing the type accordingly.
    """
    return lib in _ML_LIBS


def is_llm_lib(lib: Lib) -> t.TypeGuard[LLMLib]:
    """Check whether *lib* is a large-language-model framework.

    :param lib: Framework lib identifier.
    :return: ``True`` if *lib* is one of :data:`LLMLib`, narrowing the type accordingly.
    """
    return lib in _LLM_LIBS
