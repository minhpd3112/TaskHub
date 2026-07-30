# Hướng dẫn cài đặt công cụ Backend (Backend Setup guides)

Dưới đây là danh sách các công cụ và môi trường cần cài đặt để phát triển phần Backend của dự án:

1. **Công cụ bắt buộc (General Tools)**:
   - **Git**: Quản lý mã nguồn.
   - **Antigravity IDE**: Trình soạn thảo chính.
   - **Conda / Anaconda / Miniconda**: Quản lý môi trường Python.

2. **Kích hoạt Môi trường Phát triển (Local Python Environment)**:
   ```bash
   # Kích hoạt conda environment 'taskhub' (Python 3.12.13)
   conda activate taskhub

   # Cài đặt dependencies (nếu cần)
   pip install -r requirements.txt -r requirements-dev.txt
   ```

3. **Môi trường & Framework (Backend Environment & Framework)**:
   - [FastAPI](../docs/HuongDanCaiDat/FastAPI.md): Môi trường phát triển backend.
   - [Cẩm nang FastAPI](../docs/CamNangLapTrinh/FastAPI/README.md): Kiến thức cần nắm để lập trình backend theo hướng "AI viết code — người đặc tả và review" (đọc sau khi cài đặt xong).