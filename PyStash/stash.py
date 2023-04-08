import base64
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, NoReturn, TypeVar, Generator, Type
import inspect
import jsons
import yaml

from . import log


def fixUnicode():
    for stream in [sys.stdin, sys.stdout, sys.stderr]:
        log.dev(f'{stream.name} encoding is: {stream.encoding}')
        if stream.encoding != 'utf-8':
            log.dev(f'Reconfiguring stream {stream.name} to UTF-8 encoding.')
            stream.reconfigure(encoding='utf-8')  # type: ignore
            log.dev(f'Now {stream.name} encoding is: {stream.encoding}')


def getInput() -> dict:
    # Allows us to simply debug the script via CLI args
    if any(devArg in sys.argv for devArg in ['-i', '-dev']):
        log.enable_dev_logging()

    fixUnicode()

    if len(sys.argv) > 2 and '-i' in sys.argv:
        inputJsonFile = sys.argv[sys.argv.index('-i') + 1]

        log.debug(f'{inputJsonFile=}')
        log.debug(f'{os.path.abspath(inputJsonFile)=}')

        with open(inputJsonFile, encoding='utf-8') as s:
            stdin = s.read()
    else:
        stdin = sys.stdin.read()

    for arg in sys.argv:
        log.dev("Arg: " + arg)

    log.dev('stdin: ' + stdin)

    stashInput = json.loads(stdin)

    log.dev(f"{stashInput = }")

    return stashInput


def returnNothingFound() -> NoReturn:
    log.debug("Scraper found nothing")
    print('null', flush=True)

    sys.exit()


def scraperReturnError(msg: str = '') -> NoReturn:
    log.debug("Scraper found nothing")
    log.error(f'Scraper failed: {msg}')
    print({"error": msg}, flush=True)

    sys.exit()


def returnPluginOk() -> NoReturn:
    print({"output": "ok"}, flush=True)

    sys.exit()


def returnSceneData(sceneData: dict) -> NoReturn:
    try:
        log.debug(f"{sceneData = }")
        json.dump(sceneData, sys.stdout, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"json.dumps failed when converting scene data: {e}")

    sys.exit()


def makeImageDataBase64(image_path: str | Path):
    if not os.path.exists(image_path):
        log.warning(f"Image not found: {image_path}")
        return

    mimetypes.add_type('image/webp', '.webp')
    # type: (str,) -> str
    mime, _ = mimetypes.guess_type(image_path, strict=False)
    if not mime:
        log.warning(f"Could not get the mime type for image: {image_path}")

    if mime and not mime.startswith('image'):
        log.warning(f"Unknown mime type '{mime}' for image: {image_path}")

    with open(image_path, 'rb') as img:
        encoded = base64.b64encode(img.read()).decode()

    return 'data:{0};base64,{1}'.format(mime, encoded)


def getRelatedFiles(filePath: str | Path, maxDepth: int = 1, useFullName: bool = False) -> Generator[Path, None, None]:

    log.dev('getRelatedFiles')

    file = Path(filePath)

    baseDir = file.parent
    baseFileName = file.stem
    globPattern = baseFileName + "*"
    log.dev(globPattern)
    for p in baseDir.glob(globPattern):
        if file.exists() and p.samefile(file):
            continue
        yield p

    globPattern = ("Metadata\\" + baseFileName + "*") if useFullName else \
                  ("Metadata\\" + baseFileName[0:int(len(baseFileName)/2)] + "*")

    log.dev(globPattern)
    for p in baseDir.glob(globPattern):
        yield p

    globPattern = ("Info\\" + baseFileName + "*") if useFullName else \
                  ("Info\\" + baseFileName[0:int(len(baseFileName)/2)] + "*")

    log.dev(globPattern)
    for p in baseDir.glob(globPattern):
        yield p


def getAllSceneFiles(scene: dict[str, Any]):
    pass


def TestVideoFile(videoFile: str | Path):
    pathToCheck = str(Path(videoFile).absolute())

    ffmpegResult = subprocess.run([
        'ffmpeg.exe',
        '-hide_banner',
        '-v',
        'error',
        '-hwaccel',
        'auto',
        '-xerror',
        '-i',
        pathToCheck,
        '-f',
        'null',
        '-'
    ], capture_output=True)

    log.debug(ffmpegResult)

    if ffmpegResult.returncode != 0:
        log.error(ffmpegResult.stdout)
        log.error(ffmpegResult.stderr)
        return False

    return True


T = TypeVar('T')


def getParameters(parametersClass: Type[T]) -> T | None:
    filename = inspect.stack()[1].filename
    paramsFileName = f"{Path(filename).stem}.params.json"
    # log.info(paramsFileName)

    try:
        with open(paramsFileName, encoding='utf-8') as pf:
            return jsons.load(json.load(pf), parametersClass)
    except FileNotFoundError as fnf:
        log.debug(f"Patrameters file not found: {paramsFileName} {fnf}")

    with open(paramsFileName, encoding='utf-8', mode='w') as pf:
        empty = parametersClass()
        json.dump(jsons.dump(empty), pf, ensure_ascii=False, indent=2)

    return None


def loadParameters(filePath: str | Path):
    paramsPath = Path(filePath).with_suffix('.ymlp')
    with open(paramsPath, encoding='utf-8') as s:
        return yaml.safe_load(s)


def loadJson(path: str | Path) -> dict:
    with open(path, encoding='utf-8') as s:
        return json.load(s)
