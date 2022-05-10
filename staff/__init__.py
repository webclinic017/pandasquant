optional_module = []

from .artist import (
    Drawer,
    Gallery
)

from .analyst import (
    Regressor,
    Describer
)

from .fetcher import (
    Filer,
    Databaser,
)

from .calculator import (
    Calculator
)
    
from .processor import (
    PreProcessor
)

from .crawler import (
    StockUS
)

from .backtester import (
    Strategy,
)

# just try to import the provider
# if failed, it means the provider is not installed
try:
    from .provider import (
        Stock,
        Api
    )
    optional_module = ['Stock', 'Api']

except ImportError:
    print('[!] Data provider is not installed,' 
        ' a lot of data sources may be unavailable')


__all__ = [
    'Drawer',
    'Gallery',
    'Regressor',
    'Describer',
    'Filer',
    'Databaser',
    'StockUS',
    'Calculator',
    'PreProcessor',
    'Strategy',
    ] + optional_module