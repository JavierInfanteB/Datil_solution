-- 080: chat de Telegram de cada usuario, para mandarle sus avisos. Solo salida: el bot no recibe conversaciones.
SET search_path TO datil, public;

-- Dato personal: se guarda CIFRADO por la aplicación (AES-256-GCM, ver backend/utils/cifrado.py), nunca en claro.
-- Por eso es TEXT ("v1:" + base64) y la base no puede leerlo ni buscar por él; la clave vive en CIFRADO_DATIL.
ALTER TABLE usuarios ADD COLUMN telegram_chat_cifrado TEXT;
