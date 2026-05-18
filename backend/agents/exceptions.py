"""
Münazara — Custom Exceptions
"""


class MunazaraError(Exception):
    """Tüm Münazara hatalarının base class'ı"""
    pass


class APIQuotaError(MunazaraError):
    """API kotası bitti"""
    def __init__(self):
        super().__init__("API kotası bitti. Lütfen birkaç dakika bekleyin veya farklı bir API key deneyin.")


class APIConnectionError(MunazaraError):
    """API bağlantı hatası"""
    def __init__(self, detail: str = ""):
        msg = "Gemini API'ye bağlanılamadı."
        if detail:
            msg += f" Detay: {detail}"
        super().__init__(msg)


class APIKeyError(MunazaraError):
    """API key bulunamadı veya geçersiz"""
    def __init__(self):
        super().__init__("GEMINI_API_KEY bulunamadı! .env dosyasına geçerli bir API key yazın.")


class EmptyResponseError(MunazaraError):
    """API boş cevap döndü"""
    def __init__(self):
        super().__init__("API boş cevap döndürdü. Lütfen tekrar deneyin.")