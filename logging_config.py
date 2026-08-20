"""
Merkezi loglama yapılandırması. print() yerine bunu kullanmanın farkı:
- print() sadece terminale yazar, terminal kapanınca kaybolur
- logging, kalıcı bir dosyaya (uygulama.log) yazar, terminal kapansa
  bile geçmişte ne olduğunu görebilirsin
- Dosya belli bir boyutu (1 MB) geçince otomatik olarak döner
  (RotatingFileHandler) - tek bir dosya sonsuza kadar büyümez
"""
import logging
from logging.handlers import RotatingFileHandler

_kurulu_loggerlar = {}


def logger_al(modul_adi):
    """
    Her modül (servisler, auth, audit, bildirim) kendi adıyla bir logger
    ister: logging_config.logger_al(__name__). Aynı modül için ikinci kez
    çağrılırsa aynı logger'ı döner (tekrar handler eklemez).
    """
    if modul_adi in _kurulu_loggerlar:
        return _kurulu_loggerlar[modul_adi]

    logger = logging.getLogger(modul_adi)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = RotatingFileHandler(
            'uygulama.log', maxBytes=1_000_000, backupCount=3, encoding='utf-8'
        )
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    _kurulu_loggerlar[modul_adi] = logger
    return logger