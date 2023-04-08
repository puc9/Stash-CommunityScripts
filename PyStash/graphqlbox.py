import sys
from typing import Any

try:
    import requests
except ModuleNotFoundError:
    print(
        "You need to install the requests module. (https://docs.python-requests.org/en/latest/user/install/)",
        file=sys.stderr
    )
    print(
        "If you have pip (normally installed with python), run this command in a terminal (cmd): pip install requests",
        file=sys.stderr
    )
    sys.exit()

try:
    from . import config
    from . import log
except ModuleNotFoundError:
    print(
        (
            "You need to download the folder 'py_common' from the community repo! "
            "(CommunityScrapers/tree/master/scrapers/py_common)"
        ), file=sys.stderr
    )
    sys.exit()


# region GraphQL entry points
def _callGraphQL(endpoint, apiKey, query, variables=None) -> dict[str, Any] | None:
    headers = {
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Connection": "keep-alive",
        "DNT": "1",
        "ApiKey": apiKey
    }
    json = {
        'query': query
    }
    if variables is not None:
        json['variables'] = variables
    try:
        response = requests.post(endpoint, json=json, headers=headers)

        if response.status_code == 200:
            result = response.json()
            if result.get("error"):
                for error in result["error"]["errors"]:
                    raise Exception("GraphQL error: {}".format(error))
            if result.get("data"):
                return result.get("data")
        elif response.status_code == 401:
            log.error(f"[ERROR][GraphQL] Endpoint {endpoint} returned: HTTP Error 401, Unauthorised.")
            return None
        else:
            raise ConnectionError(f"GraphQL query failed: {endpoint}: {response.status_code} - {response.content}")
    except Exception as err:
        log.error(err)
        return None


def callGraphQL(query, variables=None):
    api_key = ""
    if config.STASH.get("api_key"):
        api_key = config.STASH["api_key"]

    if config.STASH.get("url") is None:
        log.error("You need to set the URL in 'config.py'")
        return None

    stash_url = config.STASH["url"] + "/graphql"

    return _callGraphQL(stash_url, api_key, query, variables)


def getStashBoxApiKey(endpoint) -> str | None:
    query = """
        query getstashbox {
          configuration{
            general{
              stashBoxes{
                name
                endpoint
                api_key
              }
            }
          }
        }
    """
    result = callGraphQL(query)

    if result:
        for x in result["configuration"]["general"]["stashBoxes"]:
            # log.debug(x)
            if x["endpoint"] == endpoint:
                boxapi_key = x["api_key"]
                return boxapi_key

    return None


def callStashBoxGraphQL(endpoint, query, variables=None):
    stashBoxApiKey = getStashBoxApiKey(endpoint)

    return _callGraphQL(endpoint, stashBoxApiKey, query, variables)


def configuration():
    query = """
    query Configuration {
        configuration {
            ...ConfigData
        }
    }
    fragment ConfigData on ConfigResult {
        general {
            ...ConfigGeneralData
        }
        interface {
            ...ConfigInterfaceData
        }
        dlna {
            ...ConfigDLNAData
        }
        scraping {
            ...ConfigScrapingData
        }
        defaults {
            ...ConfigDefaultSettingsData
        }
    }
    fragment ConfigGeneralData on ConfigGeneralResult {
        stashes {
            path
            excludeVideo
            excludeImage
        }
        databasePath
        generatedPath
        metadataPath
        cachePath
        calculateMD5
        videoFileNamingAlgorithm
        parallelTasks
        previewAudio
        previewSegments
        previewSegmentDuration
        previewExcludeStart
        previewExcludeEnd
        previewPreset
        maxTranscodeSize
        maxStreamingTranscodeSize
        writeImageThumbnails
        apiKey
        username
        password
        maxSessionAge
        trustedProxies
        logFile
        logOut
        logLevel
        logAccess
        createGalleriesFromFolders
        videoExtensions
        imageExtensions
        galleryExtensions
        excludes
        imageExcludes
        customPerformerImageLocation
        scraperUserAgent
        scraperCertCheck
        scraperCDPPath
        stashBoxes {
            name
            endpoint
            api_key
        }
    }
    fragment ConfigInterfaceData on ConfigInterfaceResult {
        menuItems
        soundOnPreview
        wallShowTitle
        wallPlayback
        maximumLoopDuration
        noBrowser
        autostartVideo
        autostartVideoOnPlaySelected
        continuePlaylistDefault
        showStudioAsText
        css
        cssEnabled
        language
        slideshowDelay
        disabledDropdownCreate {
            performer
            tag
            studio
        }
        handyKey
        funscriptOffset
    }
    fragment ConfigDLNAData on ConfigDLNAResult {
        serverName
        enabled
        whitelistedIPs
        interfaces
    }
    fragment ConfigScrapingData on ConfigScrapingResult {
        scraperUserAgent
        scraperCertCheck
        scraperCDPPath
        excludeTagPatterns
    }
    fragment ConfigDefaultSettingsData on ConfigDefaultSettingsResult {
        scan {
            useFileMetadata
            stripFileExtension
            scanGeneratePreviews
            scanGenerateImagePreviews
            scanGenerateSprites
            scanGeneratePhashes
            scanGenerateThumbnails
        }
        identify {
            sources {
                source {
                    ...ScraperSourceData
                }
                options {
                    ...IdentifyMetadataOptionsData
                }
            }
            options {
                ...IdentifyMetadataOptionsData
            }
        }
        autoTag {
            performers
            studios
            tags
            __typename
        }
        generate {
            sprites
            previews
            imagePreviews
            previewOptions {
                previewSegments
                previewSegmentDuration
                previewExcludeStart
                previewExcludeEnd
                previewPreset
            }
            markers
            markerImagePreviews
            markerScreenshots
            transcodes
            phashes
        }
        deleteFile
        deleteGenerated
    }
    fragment ScraperSourceData on ScraperSource {
        stash_box_index
        stash_box_endpoint
        scraper_id
    }
    fragment IdentifyMetadataOptionsData on IdentifyMetadataOptions {
        fieldOptions {
            ...IdentifyFieldOptionsData
        }
        setCoverImage
        setOrganized
        includeMalePerformers
    }
    fragment IdentifyFieldOptionsData on IdentifyFieldOptions {
        field
        strategy
        createMissing
    }
    """
    result = callGraphQL(query)
    if result:
        return result.get("configuration")
    return None

# endregion GraphQL entry points

# region Scene mangement


def getScene(scene_id):
    query = """
    query FindScene($id: ID!, $checksum: String) {
        findScene(id: $id, checksum: $checksum) {
            ...SceneData
        }
    }
    fragment SceneData on Scene {
        id
        checksum
        oshash
        title
        details
        url
        date
        rating
        o_counter
        organized
        path
        phash
        interactive
        file {
            size
            duration
            video_codec
            audio_codec
            width
            height
            framerate
            bitrate
        }
        paths {
            screenshot
            preview
            stream
            webp
            vtt
            sprite
            funscript
        }
        scene_markers {
            ...SceneMarkerData
        }
        galleries {
            ...SlimGalleryData
        }
        studio {
            ...SlimStudioData
        }
        movies {
            movie {
                ...MovieData
            }
            scene_index
        }
        tags {
            ...SlimTagData
        }
        performers {
            ...PerformerData
        }
        stash_ids {
            endpoint
            stash_id
        }
    }
    fragment SceneMarkerData on SceneMarker {
        id
        title
        seconds
        stream
        preview
        screenshot
        scene {
            id
        }
        primary_tag {
            id
            name
            aliases
        }
        tags {
            id
            name
            aliases
        }
    }
    fragment SlimGalleryData on Gallery {
        id
        checksum
        path
        title
        date
        url
        details
        rating
        organized
        image_count
        cover {
            file {
                size
                width
                height
            }
            paths {
                thumbnail
            }
        }
        studio {
            id
            name
            image_path
        }
        tags {
            id
            name
        }
        performers {
            id
            name
            gender
            favorite
            image_path
        }
        scenes {
            id
            title
            path
        }
    }
    fragment SlimStudioData on Studio {
        id
        name
        image_path
        stash_ids {
            endpoint
            stash_id
        }
        parent_studio {
            id
        }
        details
        rating
        aliases
    }
    fragment MovieData on Movie {
        id
        checksum
        name
        aliases
        duration
        date
        rating
        director
        studio {
            ...SlimStudioData
        }
        synopsis
        url
        front_image_path
        back_image_path
        scene_count
        scenes {
            id
            title
            path
        }
    }
    fragment SlimTagData on Tag {
        id
        name
        aliases
        image_path
    }
    fragment PerformerData on Performer {
        id
        checksum
        name
        url
        gender
        twitter
        instagram
        birthdate
        ethnicity
        country
        eye_color
        height
        measurements
        fake_tits
        career_length
        tattoos
        piercings
        aliases
        favorite
        image_path
        scene_count
        image_count
        gallery_count
        movie_count
        tags {
            ...SlimTagData
        }
        stash_ids {
            stash_id
            endpoint
        }
        rating
        details
        death_date
        hair_color
        weight
    }
    """

    variables = {
        "id": scene_id
    }
    result = callGraphQL(query, variables)
    if result:
        return result.get('findScene')
    return None


def getSceneFiles(scene_id):
    query = """
    query FindScene($id: ID!, $checksum: String) {
        findScene(id: $id, checksum: $checksum) {
            ...SceneData
        }
    }
    fragment SceneData on Scene {
        id
        title
        url
        date
        organized
        path
        files {
            id
            path
            basename
            parent_folder_id
            zip_file_id
            mod_time
            size
            fingerprints {
                type
                value
            }
            format
            width
            height
            duration
            video_codec
            audio_codec
            frame_rate
            bit_rate
            created_at
            updated_at
        }
    }
    """

    variables = {
        "id": scene_id
    }
    response = callGraphQL(query, variables)
    if response:
        return response.get('findScene')
    return None


def getScenePath(scene_id: str) -> str | None:
    response = callGraphQL("""
    query GetScenePathBySceneId($id: ID){
      findScene(id: $id){
        path
      }
    }""", {"id": scene_id})

    if response:
        return response.get('findScene')["path"]
    return None


def getSceneScreenshot(scene_id):
    query = """
    query FindScene($id: ID!, $checksum: String) {
        findScene(id: $id, checksum: $checksum) {
        id
        paths {
            screenshot
            }
        }
    }
    """
    variables = {
        "id": scene_id
    }
    result = callGraphQL(query, variables)
    if result:
        return result.get('findScene')
    return None


def getSceneByPerformerId(performer_id):
    query = """
        query FindScenes($filter: FindFilterType, $scene_filter: SceneFilterType, $scene_ids: [Int!]) {
          findScenes(filter: $filter, scene_filter: $scene_filter, scene_ids: $scene_ids) {
            count
            filesize
            duration
            scenes {
              ...SceneData
              __typename
            }
            __typename
          }
        }

        fragment SceneData on Scene {
          id
          checksum
          oshash
          title
          details
          url
          date
          rating
          o_counter
          organized
          path
          phash
          interactive
          interactive_speed
          captions {
            language_code
            caption_type
            __typename
          }
          created_at
          updated_at
          file {
            size
            duration
            video_codec
            audio_codec
            width
            height
            framerate
            bitrate
            __typename
          }
          paths {
            screenshot
            preview
            stream
            webp
            vtt
            sprite
            funscript
            interactive_heatmap
            caption
            __typename
          }
          scene_markers {
            ...SceneMarkerData
            __typename
          }
          galleries {
            ...SlimGalleryData
            __typename
          }
          studio {
            ...SlimStudioData
            __typename
          }
          movies {
            movie {
              ...MovieData
              __typename
            }
            scene_index
            __typename
          }
          tags {
            ...SlimTagData
            __typename
          }
          performers {
            ...PerformerData
            __typename
          }
          stash_ids {
            endpoint
            stash_id
            __typename
          }
          sceneStreams {
            url
            mime_type
            label
            __typename
          }
          __typename
        }

        fragment SceneMarkerData on SceneMarker {
          id
          title
          seconds
          stream
          preview
          screenshot
          scene {
            id
            __typename
          }
          primary_tag {
            id
            name
            aliases
            __typename
          }
          tags {
            id
            name
            aliases
            __typename
          }
          __typename
        }

        fragment SlimGalleryData on Gallery {
          id
          checksum
          path
          title
          date
          url
          details
          rating
          organized
          image_count
          cover {
            file {
              size
              width
              height
              __typename
            }
            paths {
              thumbnail
              __typename
            }
            __typename
          }
          studio {
            id
            name
            image_path
            __typename
          }
          tags {
            id
            name
            __typename
          }
          performers {
            id
            name
            gender
            favorite
            image_path
            __typename
          }
          scenes {
            id
            title
            path
            __typename
          }
          __typename
        }

        fragment SlimStudioData on Studio {
          id
          name
          image_path
          stash_ids {
            endpoint
            stash_id
            __typename
          }
          parent_studio {
            id
            __typename
          }
          details
          rating
          aliases
          __typename
        }

        fragment MovieData on Movie {
          id
          checksum
          name
          aliases
          duration
          date
          rating
          director
          studio {
            ...SlimStudioData
            __typename
          }
          synopsis
          url
          front_image_path
          back_image_path
          scene_count
          scenes {
            id
            title
            path
            __typename
          }
          __typename
        }

        fragment SlimTagData on Tag {
          id
          name
          aliases
          image_path
          __typename
        }

        fragment PerformerData on Performer {
          id
          checksum
          name
          url
          gender
          twitter
          instagram
          birthdate
          ethnicity
          country
          eye_color
          height
          measurements
          fake_tits
          career_length
          tattoos
          piercings
          aliases
          favorite
          ignore_auto_tag
          image_path
          scene_count
          image_count
          gallery_count
          movie_count
          tags {
            ...SlimTagData
            __typename
          }
          stash_ids {
            stash_id
            endpoint
            __typename
          }
          rating
          details
          death_date
          hair_color
          weight
          __typename
        }
    """
    variables = {
        "filter": {
            "page": 1,
            "per_page": 20,
            "sort": "title",
            "direction": "ASC"
        },
        "scene_filter": {
            "performers": {
                "value": [str(performer_id)],
                "modifier": "INCLUDES_ALL"
            }
        }
    }

    result = callGraphQL(query, variables)
    if result:
        return result.get('findScenes')
    return None


def getSceneIdByPerformerId(performer_id):
    query = """
        query FindScenes($filter: FindFilterType, $scene_filter: SceneFilterType, $scene_ids: [Int!]) {
          findScenes(filter: $filter, scene_filter: $scene_filter, scene_ids: $scene_ids) {
            scenes {
                id
                title
                path
                paths {
                    screenshot
                    }
                }
          }
        }
    """
    variables = {
        "filter": {
            "page": 1,
            "per_page": 20,
            "sort": "id",
            "direction": "DESC"
        },
        "scene_filter": {
            "performers": {
                "value": [str(performer_id)],
                "modifier": "INCLUDES_ALL"
            }
        }
    }

    result = callGraphQL(query, variables)
    if result:
        return result.get('findScenes')
    return None


def getScenesFilesByFilter(sceneFilter: dict, page: int = 1, perPage: int = 20) -> tuple[int, list[dict[str, Any]]] | tuple[None, None]:
    query = """
    query FindScenes($sceneFilter: SceneFilterType!, $filter: FindFilterType) {
        findScenes(scene_filter: $sceneFilter, filter: $filter) {
            count
            scenes {
                id
                title
                date
                files {
                    id
                    path
                    basename
                    mod_time
                    size
                    fingerprints {
                        type
                        value
                    }
                }
            }
        }
    }
    """

    variables = {
        "sceneFilter": sceneFilter,
        "filter": {
            "page": page,
            "per_page": perPage,
        },
    }

    result = callGraphQL(query, variables)
    if result:
        return int(result.get('findScenes').get('count')), result.get('findScenes').get('scenes')

    return None, None

# endregion Scene mangement

# region Performer mangement


def getPerformerById(performerId: int) -> dict[str, Any] | None:
    query = """
        query FindPerformer($performerId: ID!) {
          findPerformer(id: $performerId) {
            ...PerformerData
            __typename
          }
        }

        fragment PerformerData on Performer {
          id
          checksum
          name
          url
          gender
          twitter
          instagram
          birthdate
          ethnicity
          country
          eye_color
          height
          measurements
          fake_tits
          career_length
          tattoos
          piercings
          aliases
          favorite
          ignore_auto_tag
          image_path
          scene_count
          image_count
          gallery_count
          movie_count
          tags {
            ...SlimTagData
            __typename
          }
          stash_ids {
            stash_id
            endpoint
            __typename
          }
          rating
          details
          death_date
          hair_color
          weight
          __typename
        }

        fragment SlimTagData on Tag {
          id
          name
          aliases
          image_path
          __typename
        }
    """

    variables = {
        "performerId": performerId
    }

    result = callGraphQL(query, variables)
    if result:
        return result.get('findPerformer')
    return None


def getPerformersByName(performer_name):
    query = """
        query FindPerformers($filter: FindFilterType, $performer_filter: PerformerFilterType) {
          findPerformers(filter: $filter, performer_filter: $performer_filter) {
            count
            performers {
              ...PerformerData
              __typename
            }
            __typename
          }
        }

        fragment PerformerData on Performer {
          id
          checksum
          name
          url
          gender
          twitter
          instagram
          birthdate
          ethnicity
          country
          eye_color
          height
          measurements
          fake_tits
          career_length
          tattoos
          piercings
          aliases
          favorite
          ignore_auto_tag
          image_path
          scene_count
          image_count
          gallery_count
          movie_count
          tags {
            ...SlimTagData
            __typename
          }
          stash_ids {
            stash_id
            endpoint
            __typename
          }
          rating
          details
          death_date
          hair_color
          weight
          __typename
        }

        fragment SlimTagData on Tag {
          id
          name
          aliases
          image_path
          __typename
        }
    """

    variables = {
        "filter": {
            "q": performer_name,
            "page": 1,
            "per_page": 20,
            "sort": "name",
            "direction": "ASC"
        },
        "performer_filter": {}
    }

    result = callGraphQL(query, variables)
    if result:
        return result.get('findPerformers')
    return None


def getPerformersIdByName(performer_name):
    query = """
        query FindPerformers($filter: FindFilterType, $performer_filter: PerformerFilterType) {
          findPerformers(filter: $filter, performer_filter: $performer_filter) {
            count
            performers {
              ...PerformerData
            }
          }
        }

        fragment PerformerData on Performer {
          id
          name
          aliases
          }
    """

    variables = {
        "filter": {
            "q": performer_name,
            "page": 1,
            "per_page": 20,
            "sort": "name",
            "direction": "ASC"
        },
        "performer_filter": {}
    }

    result = callGraphQL(query, variables)
    if result:
        return result.get('findPerformers')
    return None


def getPerformersByNameOrAlias(nameOrAlias: str) -> dict[str, Any] | None:
    if not nameOrAlias:
        return None

    query = """
        query FindPerformers($performerFilter: PerformerFilterType) {
          findPerformers(performer_filter: $performerFilter) {
            count
            performers {
              id
              name
              aliases
            }
          }
        }
    """

    variables = {
        'performerFilter': {
            'name': {
                'modifier': 'EQUALS',
                'value': nameOrAlias
            },
            'OR': {
                'aliases': {
                    'modifier': 'INCLUDES',
                    'value': nameOrAlias
                }
            }
        }
    }

    result = callGraphQL(query, variables)
    if result:
        return result.get('findPerformers')
    return None

# endregion Performer mangement

# region Gallery mangement


def getGallery(gallery_id):
    query = """
    query FindGallery($id: ID!) {
        findGallery(id: $id) {
            ...GalleryData
        }
    }
    fragment GalleryData on Gallery {
        id
        checksum
        path
        created_at
        updated_at
        title
        date
        url
        details
        rating
        organized
        images {
            ...SlimImageData
        }
        cover {
            ...SlimImageData
        }
        studio {
            ...SlimStudioData
        }
        tags {
            ...SlimTagData
        }

        performers {
            ...PerformerData
        }
        scenes {
            ...SlimSceneData
        }
    }
    fragment SlimImageData on Image {
        id
        checksum
        title
        rating
        organized
        o_counter
        path

        file {
            size
            width
            height
            }

        paths {
            thumbnail
            image
            }

        galleries {
            id
            path
            title
            }

        studio {
            id
            name
            image_path
            }

        tags {
            id
            name
            }

        performers {
            id
            name
            gender
            favorite
            image_path
            }
    }
    fragment SlimStudioData on Studio {
        id
        name
        image_path
        stash_ids {
        endpoint
        stash_id
        }
        parent_studio {
            id
        }
        details
        rating
        aliases
    }
    fragment SlimTagData on Tag {
        id
        name
        aliases
        image_path
        }
    fragment PerformerData on Performer {
        id
        checksum
        name
        url
        gender
        twitter
        instagram
        birthdate
        ethnicity
        country
        eye_color
        height
        measurements
        fake_tits
        career_length
        tattoos
        piercings
        aliases
        favorite
        image_path
        scene_count
        image_count
        gallery_count
        movie_count

        tags {
        ...SlimTagData
        }

        stash_ids {
        stash_id
        endpoint
        }
        rating
        details
        death_date
        hair_color
        weight
    }
    fragment SlimSceneData on Scene {
        id
        checksum
        oshash
        title
        details
        url
        date
        rating
        o_counter
        organized
        path
        phash
        interactive

        file {
            size
            duration
            video_codec
            audio_codec
            width
            height
            framerate
            bitrate
        }

        paths {
            screenshot
            preview
            stream
            webp
            vtt
            chapters_vtt
            sprite
            funscript
        }

        scene_markers {
            id
            title
            seconds
            }

        galleries {
            id
            path
            title
        }

        studio {
            id
            name
            image_path
        }

        movies {
            movie {
            id
            name
            front_image_path
            }
            scene_index
        }

        tags {
            id
            name
            }

        performers {
            id
            name
            gender
            favorite
            image_path
        }

        stash_ids {
            endpoint
            stash_id
        }
    }


    """
    variables = {
        "id": gallery_id
    }
    result = callGraphQL(query, variables)
    if result:
        return result.get('findGallery')
    return None


def getGalleryPath(gallery_id):
    query = """
    query FindGallery($id: ID!) {
        findGallery(id: $id) {
            path
        }
    }
        """
    variables = {
        "id": gallery_id
    }
    result = callGraphQL(query, variables)
    if result:
        return result.get('findGallery')
    return None

# endregion Gallery mangement


# region Studio mangement

def getStashBoxStudioByName(studioName: str) -> dict[str, Any] | None:
    query = """
      query findStudioByName($name : String!) {
        findStudio(name: $name) {
          id
          name
          urls {
            url
            site {
              id
              name
              description
              url
              regex
              valid_types
              icon
              created
              updated
            }
          }
        }
      }
    """
    variables = {
        "name": studioName
    }

    result = callStashBoxGraphQL(query, variables)
    if result:
        return result.get('findStudioByName')
    return None


def findStudios(studioQuery: dict[str, Any], page=1, perPage=40):
    query = """
        query findStudiosNoStashId {
            findStudios(
                studio_filter: { is_missing: "stash_id" }
                filter: { page: 1, per_page: 40 }
            ) {
                count
    studios {
      id
      checksum
      name
      url
        query getAllStudio {
            allStudios {
                id
                name
                updated_at
                created_at
                stash_ids {
                endpoint
                stash_id
                }
            }
        }
    """
    result = callGraphQL(query)
    if result:
        # log.debug(result)
        return result["allStudios"]
    log.error('Error: make sure your _local_ stash API key (if you use one) is in pycommon config, NOT your StashDB API key. If none, make sure config is set to ""')
    sys.exit(1)

# endregion Studio mangement
