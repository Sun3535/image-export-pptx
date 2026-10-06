# image-export-pptx

PPTX 이미지를 고화질 무손실 TIFF로 추출하는 도구(pptx2tif)예요.

`.pptx` 안의 모든 이미지를 **이미지마다 각각** TIFF 파일로 저장해요.
segmentation 같은 분석에 쓸 수 있도록 화질 저하 없이 저장하는 게 목표예요.

- 슬라이드를 캡처하지 않고, pptx 안에 들어 있는 **원본 이미지 데이터**를 그대로 꺼내요.
  슬라이드에 작게 보이는 이미지도 원본 해상도로 저장돼요.
- 리사이즈하지 않아요. 압축은 무손실(deflate/lzw/none)만 써요.
- 16-bit 이미지(흑백, 컬러 모두), ICC 색 프로파일, DPI를 그대로 유지해요.
- 그룹 안의 이미지도 찾아요. 같은 이미지를 여러 번 썼다면 각각 저장해요.
- PPT에서 자르기(crop)한 이미지는 **원본 전체**를 저장하고, crop 값은 `manifest.json`에 기록해요.
- EMF/WMF 같은 벡터 이미지는 TIFF로 바꾸지 않고 원본 파일만 저장해요.

## 다른 PC에서 쓰기 (팝업 창)
1. **Python 설치** (처음 한 번): https://www.python.org/downloads/ 에서 설치해요.
   Windows에서는 설치 첫 화면의 **"Add python.exe to PATH"**를 꼭 체크해 주세요.
2. **코드 내려받기**: https://github.com/Sun3535/image-export-pptx 에서 **Code → Download ZIP**을 누른 뒤 압축을 풀어요. 로그인은 필요 없어요.
3. **실행**
   - Windows: `run_windows.bat`을 더블클릭해요.
   - Mac: `run_mac.command`를 더블클릭해요. 처음에 막히면 마우스 오른쪽 버튼 → 열기를 눌러요.
   - 처음 실행할 때는 필요한 패키지를 자동으로 설치해요(인터넷 필요).
4. **팝업 창에서**
   - 경로 칸에 PPTX 파일이나 폴더 경로를 입력하고 Enter를 눌러요.
     탐색기의 "경로로 복사"로 붙여 넣어도 돼요.
   - 또는 **[찾아보기...]**로 파일을 골라요. 여러 개를 한 번에 고를 수 있어요.
   - **[추출 시작]**을 누르면 끝나고, **[결과 폴더 열기]**로 결과를 바로 볼 수 있어요.

**저장 위치**: PPTX와 같은 폴더 안에 PPTX 이름으로 된 폴더가 만들어지고, 그 안에 TIFF가 저장돼요.
```
D:\실험\발표.pptx  →  D:\실험\발표\slide001_img01.tif ...
```

## 설치 (개발용)
```bash
pip install -e .            # 테스트까지: pip install -e ".[dev]"
pptx2tif-gui                # 팝업 창
```

## CLI
```bash
pptx2tif 발표.pptx                     # PPTX와 같은 폴더에 저장
pptx2tif 발표.pptx -o out/             # 저장 위치 지정
pptx2tif 폴더/ --recursive             # 폴더 안의 .pptx 전부
```
| 옵션 | 설명 |
|---|---|
| `--compression {deflate,lzw,none}` | 무손실 TIFF 압축 방식(기본 `deflate`) |
| `--keep-original` | pptx 안의 원본 이미지 파일(.png/.jpg 등)도 함께 저장 |
| `--min-ppi 150` | 슬라이드 기준 해상도가 이보다 낮으면 경고 |

## 출력
```
out/발표/slide001_img01.tif
out/발표/slide002_img01.tif
out/발표/slide002_img02.tif
out/발표/manifest.json
```
- 파일 이름은 `slide<슬라이드 번호>_img<슬라이드 안 순번>.tif`이에요.
- 순번은 위에서 아래, 같은 높이면 왼쪽에서 오른쪽 순서예요.
- `manifest.json`에는 이미지마다 슬라이드 번호, 원본 형식, 픽셀 크기, 비트 깊이, crop, 슬라이드 위 위치, sha256 등이 들어가요.

## Python에서 쓰기
```python
from pptx2tif import extract_images, iter_images

records = extract_images("발표.pptx", "out/")

# 파일로 저장하지 않고 numpy 배열로 바로 받기 (원본 해상도와 비트 깊이 그대로)
for rec, arr in iter_images("발표.pptx"):
    print(rec.slide_index, rec.image_index, arr.shape, arr.dtype)
```

## ⚠️ PowerPoint의 자동 이미지 압축
PowerPoint는 저장할 때 기본 설정으로 이미지를 압축해요(220ppi). 이렇게 이미 압축된 이미지는 되돌릴 수 없어요.
원본 화질을 유지하려면 PPT를 저장하기 **전에** 아래처럼 설정하세요.

**파일 → 옵션 → 고급 → 이미지 크기 및 품질 → "파일의 이미지를 압축하지 않음"** 체크

## 테스트
```bash
pytest                                       # 자동 테스트
python samples/verify.py 내덱.pptx           # 실제 pptx로 원본(samples/originals)과 픽셀 비교
```

## 라이선스
[MIT](LICENSE): 누구나 자유롭게 사용, 수정, 배포할 수 있어요.
