from enum import Enum, auto
import os
from pathlib import Path
import sys
import re
from datetime import datetime, date
from typing import Any, Callable, NamedTuple, Optional, Self

sys.path.append(os.path.abspath(r'.'))
sys.path.append(os.path.abspath(r'..'))
sys.path.append(os.path.abspath(r'../..'))
sys.path.append(os.path.abspath(r'../../..'))

try:
    import stashapi.log as log
    from stashapi.tools import human_bytes
    from stashapi.types import PhashDistance
    from stashapi.stashapp import StashInterface
    from PyStash import stash
except ModuleNotFoundError:
    print("You need to install the stashapi module. (pip install stashapp-tools)",
          file=sys.stderr)
    sys.exit(1)


pluginParams = stash.loadParameters(__file__)
stashInput = stash.getInput()

MODE = stashInput['args']['mode']
stashApp = StashInterface(stashInput["server_connection"])


class DupeTags(NamedTuple):
    # DupePrefix and Parent must be first
    DupePrefix: str
    Parent: str
    # Actual tags
    Keep: str
    Remove: str
    Ignore: str
    Check: str

    def CheckTagName(self, tagName: str) -> bool:
        if tagName == self.Parent:
            return True

        if tagName[0] != '[' or tagName[-1] != ']':
            return False

        parts = tagName.split(': ')
        if len(parts) != 2:
            return False

        dupePrefix = parts[0][1:]
        if dupePrefix != self.DupePrefix:
            return False

        return (tagName in self[2:])


dupeTagsDict = pluginParams['tags']
DUPE_TAGS = DupeTags(
    DupePrefix=dupeTagsDict.get('Prefix', 'Dupe'),
    Parent=dupeTagsDict.get('Parent', '[Library management]'),
    Keep=dupeTagsDict.get('Keep', '[Dupe: Keep]'),
    Remove=dupeTagsDict.get('Remove', '[Dupe: Remove]'),
    Ignore=dupeTagsDict.get('Ignore', '[Dupe: Ignore]'),
    Check=dupeTagsDict.get('Check', '[Dupe: To check]'),
)


class AutoNameEnum(str, Enum):

    def _generate_next_value_(name, start, count, last_values):
        return name

    def __str__(self):
        return self.name


class Sort(AutoNameEnum):
    max = auto()
    min = auto()
    list = auto()


class PropertySort(NamedTuple):
    Name: str
    Sort: Sort
    DataType: str = ''


class Priority(NamedTuple):
    Property: list[PropertySort]
    Extension: list[str]
    Codec: list[str]
    Path: list[str]


PRIORITY = Priority(
    Property=[
        PropertySort(next(iter(x.items()))[0], Sort(next(iter(x.items()))[1]))
        for x in pluginParams['priority'].get('property', [{}])
    ],
    Extension=pluginParams['priority'].get('extension', []),
    Codec=pluginParams['priority'].get('codec', []),
    Path=pluginParams['priority'].get('path', []),
)

SLIM_SCENE_FRAGMENT = """
    id
    title
    tags {
        id
        name
    }
    files {
        path
        size
        mod_time
        height
        width
        format
        bit_rate
        frame_rate
        video_codec
    }
"""


def main():
    distance = None
    match MODE:
        case "create":
            parentTag = stashApp.find_tag(DUPE_TAGS.Parent, create=True)
            parentTagId = parentTag.get('id')
            for tag in DUPE_TAGS[2:]:
                tagObject = stashApp.find_tag(tag, create=True)
                log.info(tagObject)
                if tagObject and tagObject['id'] != parentTagId:
                    stashApp.update_tag({
                        'id': tagObject['id'],
                        'ignore_auto_tag': True,
                        'parent_ids': [parentTagId]
                    })

        case "remove":
            for tag in DUPE_TAGS[2:]:
                tag_id = stashApp.find_tag(tag).get("id")
                if tag_id:
                    stashApp.destroy_tag(tag_id)

        case "cleantitle":
            clean_titles()

        case "tagexact":
            distance = PhashDistance.EXACT
        case "taghigh":
            distance = PhashDistance.HIGH
        case "tagmid":
            distance = PhashDistance.MEDIUM

        case _:
            log.exit(err=f'Unknown mode parameter: {MODE}')

    if distance != None:
        duplicate_list = stashApp.find_duplicate_scenes(distance, fragment=SLIM_SCENE_FRAGMENT)
        process_duplicates(duplicate_list)

    log.exit("Plugin exited normally.")


def parse_timestamp(ts, format="%Y-%m-%dT%H:%M:%S%z"):
    ts = re.sub(r'\.\d+', "", ts)  # remove fractional seconds
    return datetime.strptime(ts, format)


def int_or_val(value):
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
    return value


def getValueIndex(valueList: list, value, propertyName: str) -> int:
    try:
        return valueList.index(value)
    except:
        log.warning(f"could not find {propertyName} '{value}'")
        return sys.maxsize


class StashScene:

    def __init__(self, scene: dict[str, Any]) -> None:
        self.id = int(scene['id'])
        self.title = re.sub(fr'^\[{DUPE_TAGS.DupePrefix}: \d+[KR]\]\s+', '', scene['title'])
        ignoreProps = ['id', 'files', 'title']
        self.properties = {
            k: int_or_val(scene[k]) for k in scene.keys() if k not in ignoreProps
        }
        self.primaryFile = scene['files'][0] if len(scene['files']) else None
        if self.primaryFile:
            self.properties.update({
                k: int_or_val(self.primaryFile[k]) for k in self.primaryFile.keys() if k not in ignoreProps
            })
        self.reasons = list[str]()
        self.properties['resolution'] = max(self.properties['height'], self.properties['width'])
        self.properties['ext'] = self.properties['extension'] = Path(str(self.properties['path'])).suffix[1:]
        self.properties['mod_time'] = parse_timestamp(self.properties['mod_time'])

    def __repr__(self) -> str:
        return f'<StashScene ({self.id})>'

    # def __str__(self) -> str:
    #     return f'id:{self.id}, height:{self.height}, size:{human_bytes(self.size)}, file_mod_time:{self.mod_time}, title:{self.title}'

    def compare(self, other: Self) -> tuple[Self | None, str | None]:
        if not (isinstance(other, StashScene)):
            raise Exception(f"can only compare to <StashScene> not <{type(other)}>")

        # Check if same scene
        if self.id == other.id:
            return None, f"Matching IDs {self.id}=={other.id}"

        for propertySort in PRIORITY.Property:
            best, msg = self.compare_property(other, propertySort)
            if best:
                return best, msg

        return None, f"{self.id} worse than {other.id}"

    def compare_property(self, other: Self, propertySort: PropertySort, fmtFunc: Optional[Callable[[Any], str]] = None):
        selfValue = self.properties[propertySort.Name]
        otherValue = other.properties[propertySort.Name]

        if selfValue == otherValue:
            return None, None

        match propertySort.Sort:
            case Sort.list:
                priorityList = pluginParams['priority'].get(propertySort.Name, [])
                selfValueIndex = getValueIndex(priorityList, selfValue, propertySort.Name)
                otherValueIndex = getValueIndex(priorityList, otherValue, propertySort.Name)
                if selfValueIndex == otherValueIndex:
                    return None, None

                if selfValueIndex < otherValueIndex:
                    best, worst = self, other
                    bestValue, worstValue = selfValue, otherValue
                else:
                    best, worst = other, self
                    bestValue, worstValue = otherValue, selfValue

            case Sort.max:
                if not isinstance(selfValue, (int, datetime)) or not isinstance(otherValue, (int, datetime)):
                    return None, None
                if selfValue > otherValue:
                    best, worst = self, other
                    bestValue, worstValue = selfValue, otherValue
                else:
                    best, worst = other, self
                    bestValue, worstValue = otherValue, selfValue

            case Sort.min:
                if not isinstance(selfValue, (int, datetime)) or not isinstance(otherValue, (int, datetime)):
                    return None, None
                if selfValue < otherValue:
                    best, worst = self, other
                    bestValue, worstValue = selfValue, otherValue
                else:
                    best, worst = other, self
                    bestValue, worstValue = otherValue, selfValue

        # msg=f"Better Size {human_bytes(self.size)} > {human_bytes(other.size)} Δ:({human_bytes(self.size-other.size)}) | {self.id} > {other.id}"

        if not fmtFunc:
            fmtFunc = str
        return best, (
            f'Preferred {propertySort.Name} {fmtFunc(bestValue)} over {fmtFunc(worstValue)}'
            f' | {best.id} better than {worst.id}'
        )


def get_scenes_count(f: dict = {}) -> int:
    query = """
    query FindScenes($scene_filter: SceneFilterType) {
        findScenes(scene_filter: $scene_filter) {
            count
        }
    }
    """

    variables = {
        "scene_filter": f
    }

    result = stashApp._callGraphQL(query, variables)
    return result['findScenes']['count']


def process_duplicates(duplicate_list):
    ignore_tag_id = stashApp.find_tag(DUPE_TAGS.Ignore, create=True).get("id")
    check_tag_id = stashApp.find_tag(DUPE_TAGS.Check, create=True).get("id")
    filterByCheckTag = (get_scenes_count({
        'tags': {
            'modifier': 'INCLUDES',
            'value': check_tag_id
        }
    }) > 0)
    total = len(duplicate_list)
    log.info(f"There is {total} sets of duplicates found.")
    for i, group in enumerate(duplicate_list):
        log.progress(i/total)
        filtered_group = []
        for scene in group:
            tag_ids = [t['id'] for t in scene['tags']]
            if ignore_tag_id in tag_ids:
                log.debug(f"Ignore {scene['id']} {scene['title']}: marked with the ignore tag")
            elif filterByCheckTag and check_tag_id not in tag_ids:
                # log.debug(f"Ignore {scene['id']} {scene['title']}: not marked to be checked for duplicates")

                # elif not any(scene['path'].startswith(p) for p in PATH_FILTERS):
                #     log.debug(f"Ignore {scene['id']} {scene['path']}")
                # elif any(scene['path'].startswith(p) for p in EXCLUDE_PATHS):
                pass  # log.debug(f"Ignore {scene['id']} {scene['path']}")
            else:
                filtered_group.append(scene)
        if len(filtered_group) > 1:
            tag_scenes(filtered_group)


def tag_scenes(group):
    tag_keep = stashApp.find_tag(DUPE_TAGS.Keep, create=True).get("id")
    tag_remove = stashApp.find_tag(DUPE_TAGS.Remove, create=True).get("id")

    group = [StashScene(s) for s in group]

    keep_reasons = []
    keep_scene = group[0]
    for scene in group[1:]:
        better, msg = scene.compare(keep_scene)
        if better:
            keep_scene = better
        keep_reasons.append(msg)

    keep_scene.reasons = keep_reasons

    log.info(f"{keep_scene.id} best of:{[s.id for s in group]} {keep_scene.reasons}")

    for scene in group:
        if scene.id == keep_scene.id:
            # log.debug(f"Tag for Keeping: {scene.id} {scene.path}")
            stashApp.update_scenes({
                'ids': [scene.id],
                'title':  f'[{DUPE_TAGS.DupePrefix}: {keep_scene.id}K] {scene.title}',
                'tag_ids': {
                    'mode': 'ADD',
                    'ids': [tag_keep]
                }
            })
        else:
            # log.debug(f"Tag for Removal: {scene.id} {scene.path}")
            stashApp.update_scenes({
                'ids': [scene.id],
                'title':  f'[{DUPE_TAGS.DupePrefix}: {keep_scene.id}R] {scene.title}',
                'tag_ids': {
                    'mode': 'ADD',
                    'ids': [tag_remove]
                }
            })


def clean_titles():
    scenes = stashApp.find_scenes(f={
        "title": {
            "modifier": "MATCHES_REGEX",
            "value": f"^\\[{DUPE_TAGS.DupePrefix}: (\\d+)([KR])\\]"
        }
    }, fragment="id title")

    log.info(f"Cleaning Titles/Tags of {len(scenes)} Scenes ")

    for scene in scenes:
        title = re.sub(fr'\[{DUPE_TAGS.DupePrefix}: \d+[KR]\]\s+', '', scene['title'])
        log.info(
            f"Removing Dupe Title String from: [{scene['id']}] {scene['title']}")
        stashApp.update_scenes({
            'ids': [scene['id']],
            'title': title
        })

    tag_keep = stashApp.find_tag(DUPE_TAGS.Keep)
    if tag_keep:
        tag_keep = tag_keep['id']
        scenes = stashApp.find_scenes(f={
            "tags": {
                "value": [tag_keep],
                "modifier": "INCLUDES",
                "depth": 0
            }
        }, fragment="id title")
        stashApp.update_scenes({
            'ids': [s['id'] for s in scenes],
            'tag_ids': {
                'mode': 'REMOVE',
                'ids': [tag_keep]
            }
        })

    tag_remove = stashApp.find_tag(DUPE_TAGS.Remove)
    if tag_remove:
        tag_remove = tag_remove['id']
        scenes = stashApp.find_scenes(f={
            "tags": {
                "value": [tag_remove],
                "modifier": "INCLUDES",
                "depth": 0
            }
        }, fragment="id title")
        stashApp.update_scenes({
            'ids': [s['id'] for s in scenes],
            'tag_ids': {
                'mode': 'REMOVE',
                'ids': [tag_remove]
            }
        })


group = [
    stashApp.find_scene(63196, SLIM_SCENE_FRAGMENT),
    stashApp.find_scene(8955, SLIM_SCENE_FRAGMENT),
    stashApp.find_scene(8952, SLIM_SCENE_FRAGMENT)
]

if __name__ == '__main__':
    main()
