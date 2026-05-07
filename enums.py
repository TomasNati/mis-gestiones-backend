from enum import Enum


class InstrumentoTipo(str, Enum):
    CEDEAR = "CEDEAR"
    FCI = "FCI"
    ON = "ON"
    ACCION_LOCAL = "ACCION_LOCAL"
    ACCION_INTERNACIONAL = "ACCION_INTERNACIONAL"
    BONO = "BONO"
    FCI_EXTERIOR = "FCI_EXTERIOR"
    ETF = "ETF",
    CRIPTO = "CRIPTO",

class ClaseRenta(str, Enum):
    FIJA = "FIJA"
    VARIABLE = "VARIABLE"
    MIXTA = "MIXTA"


class Moneda(str, Enum):
    PESO = "PESO"
    DOLAR = "DOLAR"
    DOLAR_CCL = "DOLAR_CCL"

class Broker(str, Enum):
    PPI= "PPI",
    BALANZ = "BALANZ",

# Utility to export values (useful for future endpoints)
def instrumento_tipo_values():
    return [e.value for e in InstrumentoTipo]


def clase_renta_values():
    return [e.value for e in ClaseRenta]


def moneda_values():
    return [e.value for e in Moneda]

def broker_values():    
    return [e.value for e in Broker]
