# 로컬 글꼴

화면은 Outfit과 Noto Sans KR을 사용합니다. 실행 중 외부 글꼴 서버에 연결하지 않도록 WOFF2 파일을 함께 제공합니다.

| 글꼴 | 공식 원본 | 라이선스 |
| --- | --- | --- |
| Outfit | [Google Fonts 원본](https://github.com/google/fonts/tree/main/ofl/outfit) | [SIL OFL 1.1](../ops_workflow_lab/static/fonts/outfit-OFL.txt) |
| Noto Sans KR | [Google Fonts 원본](https://github.com/google/fonts/tree/main/ofl/notosanskr) | [SIL OFL 1.1](../ops_workflow_lab/static/fonts/notosanskr-OFL.txt) |

공식 저장소의 가변 TTF를 fontTools로 필요한 유니코드 범위에 맞춰 WOFF2로 변환했습니다. Outfit은 라틴·문장부호·화살표를, Noto Sans KR은 라틴·한글 음절·자모·문장부호를 포함합니다. 글꼴 이름과 저작권 메타데이터를 보존했습니다. 회사 소스, 운영 데이터, 제품 로고는 포함하지 않습니다.

공개 파일 검사는 글꼴과 라이선스 네 파일의 검토된 SHA-256을 확인합니다. 글꼴을 갱신하면 출처·라이선스·해시를 함께 검토해야 합니다. 아이콘은 이 데모에서 작성한 간단한 SVG 도형입니다.
