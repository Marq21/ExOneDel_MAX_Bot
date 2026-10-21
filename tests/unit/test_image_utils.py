import pytest
from unittest.mock import patch, Mock
import numpy as np
from src.utils.image_utils import (
    extract_code_from_image,
    extract_code_from_image_async,
)
from src.utils.generate_codes import (
    generate_barcode_image_bytesio,
    generate_qr_code_image_bytesio,
)

# ─────────────────────────────────────────────
# Синхронная функция
# ─────────────────────────────────────────────

class TestExtractCodeFromImageSync:
    """Тесты синхронного распознавания кодов."""

    def test_extract_code128(self):
        """Распознавание CODE128 (OZON)."""
        mock_image_data = b"fake_image_bytes"
        
        with patch("cv2.imdecode") as mock_imdecode:
            # Фейковое OpenCV-изображение
            fake_image = np.array([[[1, 2, 3]]], dtype=np.uint8)
            mock_imdecode.return_value = fake_image
            
            with patch("pyzbar.pyzbar.decode") as mock_decode:
                # Фейковый объект с CODE128
                fake_obj = Mock()
                fake_obj.type = 'CODE128'
                fake_obj.data = b'12345*6789'
                mock_decode.return_value = [fake_obj]
                
                result = extract_code_from_image(mock_image_data)
                assert result == "12345*6789"

    def test_extract_qrcode(self):
        """Распознавание QRCODE (Wildberries)."""
        mock_image_data = b"fake_image_bytes"
        
        with patch("cv2.imdecode") as mock_imdecode:
            fake_image = np.array([[[1, 2, 3]]], dtype=np.uint8)
            mock_imdecode.return_value = fake_image
            
            with patch("pyzbar.pyzbar.decode") as mock_decode:
                fake_obj = Mock()
                fake_obj.type = 'QRCODE'
                fake_obj.data = b'12345_6789'
                mock_decode.return_value = [fake_obj]
                
                result = extract_code_from_image(mock_image_data)
                assert result == "12345_6789"

    def test_no_code_found(self):
        """Когда на изображении нет кодов."""
        mock_image_data = b"fake_image_bytes"
        
        with patch("cv2.imdecode") as mock_imdecode:
            fake_image = np.array([[[1, 2, 3]]], dtype=np.uint8)
            mock_imdecode.return_value = fake_image
            
            with patch("pyzbar.pyzbar.decode") as mock_decode:
                # Пустой список — кодов нет
                mock_decode.return_value = []
                
                result = extract_code_from_image(mock_image_data)
                assert result is None

    def test_unsupported_barcode_type(self):
        """Когда найден код неподдерживаемого типа (например, EAN13)."""
        mock_image_data = b"fake_image_bytes"
        
        with patch("cv2.imdecode") as mock_imdecode:
            fake_image = np.array([[[1, 2, 3]]], dtype=np.uint8)
            mock_imdecode.return_value = fake_image
            
            with patch("pyzbar.pyzbar.decode") as mock_decode:
                fake_obj = Mock()
                fake_obj.type = 'EAN13'  # Не CODE128 и не QRCODE
                fake_obj.data = b'4607008155441'
                mock_decode.return_value = [fake_obj]
                
                result = extract_code_from_image(mock_image_data)
                assert result is None

    def test_invalid_image_bytes(self):
        """Когда байты не являются валидным изображением."""
        invalid_bytes = b"not_an_image"
        
        with patch("cv2.imdecode") as mock_imdecode:
            # imdecode возвращает None для невалидных данных
            mock_imdecode.return_value = None
            
            result = extract_code_from_image(invalid_bytes)
            assert result is None

    def test_unicode_decode_error(self):
        """Когда данные кода не декодируются в UTF-8."""
        mock_image_data = b"fake_image_bytes"
        
        with patch("cv2.imdecode") as mock_imdecode:
            fake_image = np.array([[[1, 2, 3]]], dtype=np.uint8)
            mock_imdecode.return_value = fake_image
            
            with patch("pyzbar.pyzbar.decode") as mock_decode:
                fake_obj = Mock()
                fake_obj.type = 'CODE128'
                # Невалидные UTF-8 байты
                fake_obj.data = b'\xff\xfe\xfd'
                mock_decode.return_value = [fake_obj]
                
                result = extract_code_from_image(mock_image_data)
                assert result is None

    def test_multiple_codes_returns_first_valid(self):
        """Когда на изображении несколько кодов — возвращается первый валидный."""
        mock_image_data = b"fake_image_bytes"
        
        with patch("cv2.imdecode") as mock_imdecode:
            fake_image = np.array([[[1, 2, 3]]], dtype=np.uint8)
            mock_imdecode.return_value = fake_image
            
            with patch("pyzbar.pyzbar.decode") as mock_decode:
                # Первый — неподдерживаемый тип
                fake_obj1 = Mock()
                fake_obj1.type = 'EAN13'
                fake_obj1.data = b'4607008155441'
                
                # Второй — валидный CODE128
                fake_obj2 = Mock()
                fake_obj2.type = 'CODE128'
                fake_obj2.data = b'12345*6789'
                
                mock_decode.return_value = [fake_obj1, fake_obj2]
                
                result = extract_code_from_image(mock_image_data)
                assert result == "12345*6789"


# ─────────────────────────────────────────────
# Асинхронная обёртка
# ─────────────────────────────────────────────

@pytest.mark.asyncio
class TestExtractCodeFromImageAsync:
    """Тесты асинхронного распознавания кодов."""

    async def test_async_extract_code128(self):
        """Async-обёртка распознаёт CODE128."""
        mock_image_data = b"fake_image_bytes"
        
        with patch("cv2.imdecode") as mock_imdecode:
            fake_image = np.array([[[1, 2, 3]]], dtype=np.uint8)
            mock_imdecode.return_value = fake_image
            
            with patch("pyzbar.pyzbar.decode") as mock_decode:
                fake_obj = Mock()
                fake_obj.type = 'CODE128'
                fake_obj.data = b'12345*6789'
                mock_decode.return_value = [fake_obj]
                
                result = await extract_code_from_image_async(mock_image_data)
                assert result == "12345*6789"

    async def test_async_extract_qrcode(self):
        """Async-обёртка распознаёт QRCODE."""
        mock_image_data = b"fake_image_bytes"
        
        with patch("cv2.imdecode") as mock_imdecode:
            fake_image = np.array([[[1, 2, 3]]], dtype=np.uint8)
            mock_imdecode.return_value = fake_image
            
            with patch("pyzbar.pyzbar.decode") as mock_decode:
                fake_obj = Mock()
                fake_obj.type = 'QRCODE'
                fake_obj.data = b'12345_6789'
                mock_decode.return_value = [fake_obj]
                
                result = await extract_code_from_image_async(mock_image_data)
                assert result == "12345_6789"

    async def test_async_no_code_found(self):
        """Async-обёртка возвращает None, если кодов нет."""
        mock_image_data = b"fake_image_bytes"
        
        with patch("cv2.imdecode") as mock_imdecode:
            fake_image = np.array([[[1, 2, 3]]], dtype=np.uint8)
            mock_imdecode.return_value = fake_image
            
            with patch("pyzbar.pyzbar.decode") as mock_decode:
                mock_decode.return_value = []
                
                result = await extract_code_from_image_async(mock_image_data)
                assert result is None

    async def test_async_empty_bytes_returns_none(self):
        """Async-обёртка возвращает None для пустых байтов."""
        result = await extract_code_from_image_async(b"")
        assert result is None

    async def test_async_none_returns_none(self):
        """Async-обёртка возвращает None для None."""
        result = await extract_code_from_image_async(None)
        assert result is None

    def test_invalid_image_bytes_real(self):
        """Тест с реальными невалидными байтами (без мока)."""
        # Случайные байты, которые точно не являются изображением
        invalid_bytes = b"this_is_not_an_image_at_all" * 100
        
        result = extract_code_from_image(invalid_bytes)
        assert result is None


class TestRoundTrip:
    """Интеграционные тесты: генерация → распознавание."""

    def test_barcode_round_trip(self):
        """Сгенерированный CODE128 должен распознаваться обратно."""
        original_code = "12345*6789"
        
        # Генерируем изображение
        image_bytesio = generate_barcode_image_bytesio(original_code)
        assert image_bytesio is not None
        
        # Получаем байты
        image_bytes = image_bytesio.getvalue()
        
        # Распознаём код
        extracted_code = extract_code_from_image(image_bytes)
        
        # Должны получить тот же код
        assert extracted_code == original_code

    def test_qr_code_round_trip(self):
        """Сгенерированный QR-код должен распознаваться обратно."""
        original_code = "12345_6789_XYZ"
        
        # Генерируем изображение
        image_bytesio = generate_qr_code_image_bytesio(original_code)
        assert image_bytesio is not None
        
        # Получаем байты
        image_bytes = image_bytesio.getvalue()
        
        # Распознаём код
        extracted_code = extract_code_from_image(image_bytes)
        
        # Должны получить тот же код
        assert extracted_code == original_code

    def test_barcode_round_trip_async(self):
        """Async-версии тоже работают в цепочке."""
        import asyncio
        from src.utils.generate_codes import generate_barcode_image_async
        from src.utils.image_utils import extract_code_from_image_async
        
        async def run_test():
            original_code = "TEST*123"
            image_bytesio = await generate_barcode_image_async(original_code)
            assert image_bytesio is not None
            
            extracted_code = await extract_code_from_image_async(image_bytesio.getvalue())
            assert extracted_code == original_code
        
        asyncio.run(run_test())

    def test_qr_code_round_trip_async(self):
        """Async-версии QR тоже работают в цепочке."""
        import asyncio
        from src.utils.generate_codes import generate_qr_code_async
        from src.utils.image_utils import extract_code_from_image_async
        
        async def run_test():
            original_code = "TEST_123_ABC"
            image_bytesio = await generate_qr_code_async(original_code)
            assert image_bytesio is not None
            
            extracted_code = await extract_code_from_image_async(image_bytesio.getvalue())
            assert extracted_code == original_code
        
        asyncio.run(run_test())