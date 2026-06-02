import warnings

warnings.filterwarnings(
    "ignore",
    message=r"builtin type SwigPy.* has no __module__ attribute",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"builtin type swigvarlink has no __module__ attribute",
    category=DeprecationWarning,
)
