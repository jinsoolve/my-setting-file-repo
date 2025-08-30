vs-code에서 cpp의 snippet 기능을 위한 코드들 입니다.

# cpp.json

vs-code에서 cpp의 snippet을 위한 설정 파일입니다.

보통 `'~/Library/Application Support/Code/User/snippets/cpp.json'` 에 위치해 있습니다.

# converter-xml-to-json.py

clion의 live template을 vs-code의 cpp.json으로 바꿔주는 코드입니다.

## Logic

### input path (clion xml)

clion의 live template의 xml 파일은 `"~/Library/Application Support/JetBrains/CLion2025.1/templates/C_C__.xml"` 보통 이 위치에 있습니다.

위 코드에서는 `JETBRAINS_DIR + "Clion{version}" + CLION_TEMPLATE_FILE` 이런 식으로 해당 경로를 구성하고 있습니다.

만약 위치가 다르다면 해당 상수값을 수정하면 됩니다.

### output path (vscode json)

vs-code의 snippets의 json 파일은 `"~/Library/Application Support/Code/User/snippets/cpp.json"` 이 위치로 설정되어 있습니다.

위 코드에서는 `VSCODE_SNIPPET_PATH` 에 그 값이 저장되어 있습니다.

만약 위치가 다르다면 해당 상수 값을 수정하면 됩니다.

### .settings-converter-xml-to-json.json

사용자가 최근에 설정한 Clion의 Version 값이 저장되어 있는 파일입니다.  
저장 위치는 `converter-xml-to-json.py` 파일이 있는 위치와 동일합니다.

만약 해당 파일이 없으면 자동으로 가장 최신 버전의 clion version을 갖고 옵니다.

## How to use

1. input(clion xml)과 output(vs-code xml) 위치를 확인합니다. 그에 알맞게 위치를 수정합니다.
2. 코드를 실행시키면, 터미널에 나타난 프롬프트에 알맞게 입력하면 됩니다.
