// Common Patterns
var patterns = {
  movieTitleAndYear: /(.+) \(\d{4}\)/,
  sceneTitleAndPerformers: /(.+) - ([A-zÀ-ú, ]+)/
}

var rules = [
  {
    name: 'Rule 1',
    pattern: [
      'Specific Studio',
      null,
      null
    ],
    fields: {
      studio: '#0',
      title: '#2',
    }
  },
  {
    name: 'Rule 2',
    pattern: [
      ['One Studio', 'Another Studio'],
      patterns.movieTitleAndYear,
      patterns.sceneTitleAndPerformers
    ],
    fields: {
      title: '#2',
      studio: '#0',
      performers: '#3'
    }
  },
  {
    name: 'Scrape Rule 1',
    pattern: [
      ['One Studio', 'Another Studio'],
      patterns.movieTitleAndYear,
      patterns.sceneTitleAndPerformers
    ],
    scrapeWith: 'scrapper-id',
  },
  {
    name: 'Skip Rule 1',
    pattern: [
      ['One Studio', 'Another Studio'],
      patterns.movieTitleAndYear,
      patterns.sceneTitleAndPerformers
    ],
    skip: true,
  },
];

/* ----------------------------------------------------------------------------
// DO NOT EDIT BELOW!
---------------------------------------------------------------------------- */
function main()
{
  try
  {
    switch (getTask(input.Args))
    {
      case 'createTags':
        var runTag = getArg(input.Args, 'runTag');
        var testTag = getArg(input.Args, 'testTag');
        createTags([runTag, testTag]);
        break;

      case 'removeTags':
        var runTag = getArg(input.Args, 'runTag');
        var testTag = getArg(input.Args, 'testTag');
        removeTags([runTag, testTag]);
        break;

      case 'cleanScenesTags':
        var runTag = getArg(input.Args, 'runTag');
        var testTag = getArg(input.Args, 'testTag');
        cleanScenesTags([runTag, testTag]);
        break;

      case 'runRules':
        var runTag = getArg(input.Args, 'runTag');
        initBasePaths();
        runRules(runTag);
        break;

      case 'testRules':
        DEBUG = true;
        var testTag = getArg(input.Args, 'testTag');
        initBasePaths();
        runRules(testTag);
        break;

      case 'scene':
        var id = getId(input.Args);
        initBasePaths();
        matchRuleWithSceneId(id, applyRule, true);
        break;

      case 'image':
        var id = getId(input.Args);
        initBasePaths();
        break;

      default:
        throw 'Unsupported task';
    }
  }
  catch (e)
  {
    return { Output: 'error', Error: e };
  }

  return { Output: 'ok' };
}

// Get an input arg
function getArg(inputArgs, arg)
{
  if (inputArgs.hasOwnProperty(arg))
  {
    return inputArgs[arg];
  }

  throw 'Input is missing ' + arg;
}

// Determine task based on input args
function getTask(inputArgs)
{
  if (inputArgs.hasOwnProperty('task'))
  {
    return inputArgs.task;
  }

  if (!inputArgs.hasOwnProperty('hookContext'))
  {
    return;
  }

  switch (inputArgs.hookContext.type)
  {
    case 'Scene.Create.Post':
      return 'scene';

    case 'Image.Create.Post':
      return 'image';
  }
}

// Get stash paths from configuration
function initBasePaths()
{
  var query = '\
  query Query {\
    configuration {\
      general {\
        stashes {\
          path\
        }\
      }\
    }\
  }';

  var result = gql.Do(query);
  if (!result.configuration)
  {
    throw 'Unable to get library paths';
  }

  BASE_PATHS = result.configuration.general.stashes.map(function (stash)
  {
    return stash.path;
  });

  if (BASE_PATHS == null || BASE_PATHS.length == 0)
  {
    throw 'Unable to get library paths';
  }
}

// Create tag if it does not already exist
function createTags(tags)
{
  var query = '\
  mutation TagCreate($input: TagCreateInput!) {\
    tagCreate(input: $input) {\
      id\
    }\
  }';

  tags.forEach(function (tag)
  {
    if (tryGetTag(tag) !== null)
    {
      log.Info('[PathParser] Tag "' + tag + '" is already present.');
      return;
    }

    var variables = {
      input: {
        name: tag
      }
    };

    var result = gql.Do(query, variables);
    if (result.tagCreate)
    {
      log.Info('[PathParser] Created tag ' + tag + ' with ID: ' + result.tagCreate["id"]);
    }
    else
    {
      throw 'Could not create tag ' + tag;
    }
  });
}

// Remove tags if it already exists
function removeTags(tags)
{
  tags.forEach(function (tag)
  {
    var tagId = tryGetTag(tag);
    if (tagId === null)
    {
      return;
    }

    var query = '\
    mutation TagsDestroy($ids: [ID!]!) {\
      tagsDestroy(ids: $ids)\
    }';

    var variables = {
      ids: [tagId]
    };

    var result = gql.Do(query, variables);
    if (result.tagsDestroy)
    {
      log.Info('[PathParser] Removed tag ' + tag + ' with ID: ' + tagId);
    }
    else
    {
      throw 'Unable to remove tag ' + tag;
    }
  });
}

// Remove tags from scenes
function cleanScenesTags(tags)
{
  var tagIds = tags.map(tryGetTag).filter(notNull);

  if (!tagIds || tagIds.count == 0)
  {
    log.Info("[PathParser] No tags found.");
    return;
  }

  var taggedScenesQuery = '\
  query FindTaggedScenes($taggedSceneFilter: SceneFilterType, $filterType: FindFilterType) {\
    findScenes(scene_filter: $taggedSceneFilter, filter: $filterType) {\
      count\
      scenes {\
        id\
      }\
    }\
  }';

  var cleanTagsQuery = '\
  mutation cleanTagsQuery($removeTags: BulkSceneUpdateInput!) {\
    bulkSceneUpdate(input: $removeTags) {\
      id\
    }\
  }\
  ';

  var totalSceneFound = 0;
  var cleanedScenesCount = 0;
  var firstRun = true;
  var prettyTagsToRemove = "['" + tags.join("', '") + "']"

  while (true)
  {
    var taggedScenesVariables = {
      taggedSceneFilter: {
        tags: {
          modifier: 'INCLUDES',
          value: tagIds
        }
      }
    };

    log.Debug(taggedScenesQuery);
    log.Debug(taggedScenesVariables);
    var taggedScenes = gql.Do(taggedScenesQuery, taggedScenesVariables);
    log.Debug(taggedScenes);
    if (!taggedScenes.findScenes || (taggedScenes.findScenes.scenes.length == 0 && firstRun))
    {
      log.Info("[PathParser] No scenes tagged with: " + prettyTagsToRemove);
    }

    if (firstRun)
    {
      totalSceneFound = taggedScenes.findScenes.count;
      firstRun = false;
    }

    var returnedCount = taggedScenes.findScenes.scenes.length;
    if (returnedCount == 0)
    {
      break;
    }

    var sceneIds = taggedScenes.findScenes.scenes.map(function (s) { return s.id; });

    log.Debug(sceneIds);

    var cleanTagsVariables = {
      removeTags: {
        ids: sceneIds,
        tag_ids: {
          ids: tagIds,
          mode: "REMOVE",
        }
      }
    };

    log.Debug(taggedScenesQuery);
    log.Debug(cleanTagsVariables);
    var cleanedScenes = gql.Do(cleanTagsQuery, cleanTagsVariables);
    log.Debug(cleanedScenes);
    cleanedScenesCount += cleanedScenes.bulkSceneUpdate.length
    log.Progress(cleanedScenesCount / totalSceneFound);
  }

  if (totalSceneFound > 0)
  {
    log.Info('[PathParser] Removed tags ' + prettyTagsToRemove +
      ' from ' + cleanedScenesCount + ' scenes out of ' + totalSceneFound + ' found.');
  }
}

// Run rules for scenes containing tag
function runRules(tag)
{
  var tagId = tryGetTag(tag);
  if (tagId === null)
  {
    throw 'Tag ' + tag + ' does not exist';
  }

  log.Info('[PathParser] Start processing scenes marked with tag: ' + tag);

  var query = '\
  query FindScenes($sceneFilter: SceneFilterType, $filterType: FindFilterType) {\
    findScenes(scene_filter: $sceneFilter, filter: $filterType) {\
      count\
      scenes {\
        id\
      }\
    }\
  }';

  var currentPage = 1;
  var processedSceneCount = 0;
  var totalSceneFound = 0;
  var progress = 0;
  var firstRun = true;

  do
  {
    var variables = {
      sceneFilter: {
        tags: {
          value: tagId,
          modifier: 'INCLUDES'
        }
      },
      filterType: {
        page: currentPage,
        per_page: 20
      }
    };

    var result = gql.Do(query, variables);
    if (!result.findScenes || (result.findScenes.scenes.length == 0 && firstRun))
    {
      throw 'No scenes found with tag ' + tag;
    }

    if (firstRun)
    {
      totalSceneFound = result.findScenes.count;
      firstRun = false;
    }

    var returnedCount = result.findScenes.scenes.length;

    if (!returnedCount)
    {
      break;
    }

    log.Debug('Processing ' + returnedCount + ' scenes')
    result.findScenes.scenes.forEach(function (scene)
    {
      matchRuleWithSceneId(scene.id, applyRule, false);

      progress++;

      log.Progress(progress / totalSceneFound);
    });

    processedSceneCount += returnedCount;
    currentPage++;

  } while (returnedCount > 0);


  if (processedSceneCount > 0)
  {
    log.Info('[PathParser] Processed: ' + processedSceneCount + ' scenes out of ' + totalSceneFound + ' found.');
  }

  log.Info('[PathParser] Done processing scenes marked with tag: ' + tag);
}

// Get scene/image id from input args
function getId(inputArgs)
{
  if ((id = inputArgs.hookContext.id) == null)
  {
    throw 'Input is missing id';
  }

  return id;
}

// Apply callback function to first matching rule for id
function matchRuleWithSceneId(sceneId, cb, onHookCall)
{
  var query = '\
  query FindScene($findSceneId: ID) {\
    findScene(id: $findSceneId) {\
      files {\
        path\
      }\
    }\
  }';

  var variables = {
    findSceneId: sceneId
  }

  var result = gql.Do(query, variables);
  if (!result.findScene || result.findScene.files.length == 0)
  {
    throw 'Missing scene for id: ' + sceneId;
  }

  var firstPathFound = null;
  for (var i = 0; i < result.findScene.files.length; i++)
  {
    if (!firstPathFound)
    {
      firstPathFound = result.findScene.files[i].path;
    }

    try
    {
      matchRuleWithPath(sceneId, result.findScene.files[i].path, cb);

      if (DEBUG && bufferedOutput !== null && bufferedOutput !== '')
      {
        log.Info('[PathParser] ' + bufferedOutput);
      }

      return;
    }
    catch (e)
    {
      log.Debug(e);
      continue;
    }
  }

  if (DEBUG && bufferedOutput !== null && bufferedOutput !== '')
  {
    log.Info('[PathParser] ' + bufferedOutput);
  }

  var msg = '[PathParser] No rule matches id: ' + sceneId;

  if (firstPathFound !== null)
  {
    msg += '\nPath: ' + firstPathFound;
  }

  if (onHookCall)
  {
    log.Debug(msg);
  }
  else
  {
    log.Warn(msg);
  }
}

// Apply callback to first matching rule for path
function matchRuleWithPath(sceneId, scenePath, cb)
{
  // Remove extension from filename
  fullPathNoExt = scenePath.slice(0, scenePath.lastIndexOf('.'));

  // Remove base path
  var libraryPath = fullPathNoExt;
  for (var i = 0; i < BASE_PATHS.length; i++)
  {
    if (libraryPath.slice(0, BASE_PATHS[i].length) === BASE_PATHS[i])
    {
      libraryPath = libraryPath.slice(BASE_PATHS[i].length);
      while (libraryPath[0] === '\\')
      {
        libraryPath = libraryPath.slice(1);
      }
    }
  }

  if (DEBUG)
  {
    bufferedOutput = libraryPath + '\n';
  }

  // Split the paths into parts
  var allParts = fullPathNoExt.split(/[\\/]/);
  var partsInLib = libraryPath.split(/[\\/]/);

  for (var i = 0; i < rules.length; i++)
  {
    var currentRule = rules[i];
    var partsToTest = currentRule.includesBasePath ? allParts : partsInLib;
    var sceneData = testRule(currentRule.pattern, partsToTest);
    if (sceneData !== null)
    {
      if (DEBUG)
      {
        bufferedOutput += 'Matched rule: ' + currentRule.name + '\n';
      }

      log.Debug('[PathParser]\nMatched rule: ' + currentRule.name + '\nFor path: ' + scenePath);
      cb(sceneId, scenePath, currentRule, sceneData);

      return;
    }
  }

  bufferedOutput += 'No matching rule!';
  throw 'No matching rule for path: ' + scenePath;
}

// Test single rule
function testRule(pattern, parts)
{
  if (pattern.length !== parts.length)
  {
    return null;
  }

  var matchedParts = [];
  for (var i = 0; i < pattern.length; i++)
  {
    if ((subMatches = testPattern(pattern[i], parts[i])) == null)
    {
      return null;
    }

    matchedParts = [].concat(matchedParts, subMatches);
  }

  return matchedParts;
}

function testPattern(pattern, part)
{
  // Match anything
  if (pattern == null)
  {
    return [part];
  }

  // Simple match
  if (typeof pattern === 'string')
  {
    if (pattern === part)
    {
      return [part];
    }

    return null;
  }

  // Predicate match
  if (typeof pattern == 'function')
  {
    try
    {
      var results = pattern(part);
      if (results !== null)
      {
        return results;
      }
    }
    catch (e)
    {
      throw e;
    }

    return null;
  }

  // Array match
  if (pattern instanceof Array)
  {
    for (var i = 0; i < pattern.length; i++)
    {
      if ((results = testPattern(pattern[i], part)) != null)
      {
        return results;
      }
    }

    return null;
  }

  // RegExp match
  if (pattern instanceof RegExp)
  {
    var results = pattern.exec(part);
    if (results === null)
    {
      return null;
    }

    return results.slice(1);
  }
}

// Apply rule
function applyRule(sceneId, scenePath, rule, data)
{
  if (rule.skip === true)
  {
    if (DEBUG)
    {
      bufferedOutput += 'Skipping scene: ' + sceneId + '\n';
    }
    else
    {
      log.Info('[PathParser] Rule: ' + rule.name +
        '\nPath: ' + scenePath +
        '\nSkipping scene: ' + sceneId);
    }

    return;
  }

  if (rule.scrapeWith)
  {
    callScrapper(sceneId, scenePath, rule, data);
    return;
  }

  setFields(sceneId, scenePath, rule, data);
}

function callScrapper(sceneId, scenePath, rule, data)
{
  var query = '\
  mutation RunScrapper($input: IdentifyMetadataInput!) {\
    metadataIdentify(input: $input)\
  }';

  var variables = {
    input: {
      sources: [{ source: { scraper_id: rule.scrapeWith } }],
      options: {
        fieldOptions: [
          {
            field: "title",
            strategy: "OVERWRITE",
            createMissing: null
          },
          {
            field: "performers",
            strategy: "MERGE",
            createMissing: true
          },
          {
            field: "studio",
            strategy: "OVERWRITE",
            createMissing: true
          },
          {
            field: "tags",
            strategy: "MERGE",
            createMissing: true
          },
          {
            field: "stash_ids",
            strategy: "IGNORE",
            createMissing: false
          },
          {
            field: "date",
            strategy: "OVERWRITE",
            createMissing: false
          },
          {
            field: "details",
            strategy: "OVERWRITE",
            createMissing: false
          },
          {
            field: "url",
            strategy: "OVERWRITE",
            createMissing: false
          },
          {
            field: "code",
            strategy: "OVERWRITE",
            createMissing: false
          },
          {
            field: "director",
            strategy: "OVERWRITE",
            createMissing: false
          }
        ],
        setCoverImage: true,
        setOrganized: false,
        includeMalePerformers: true
      },
      sceneIDs: [
        sceneId
      ]
    }
  };

  // Test only
  if (DEBUG)
  {
    bufferedOutput += 'Would call scrapper ' + rule.scrapeWith +
      ' on scene ' + scenePath +
      ' ID ' + sceneId +
      '\n';

    return;
  }

  var result = gql.Do(query, variables);
  if (result.metadataIdentify)
  {
    log.Info('[PathParser] Rule: ' + rule.name +
      '\nPath: ' + scenePath +
      '\nCalled scrapper ' + rule.scrapeWith + ' on scene: ' + sceneId);

  }
  else
  {
    throw 'Unable to run scrapper ' + rule.scrapeWith + ' for scene ' + sceneId;
  }
}

// Set the fields
function setFields(sceneId, scenePath, rule, data)
{
  var any = false;
  var variables = {
    input: {
      id: sceneId
    }
  };

  if (DEBUG)
  {
    for (var i = 0; i < data.length; i++)
    {
      bufferedOutput += '#' + i + ': ' + data[i] + '\n';
    }
  }

  var fields = rule.fields;

  for (var field in fields)
  {
    var value = fields[field];
    for (var i = data.length - 1; i >= 0; i--)
    {
      value = value.replace('#' + i, data[i]);
    }

    switch (field)
    {
      case 'title':
        if (DEBUG)
        {
          bufferedOutput += field + ': ' + value + '\n';
        }

        variables.input['title'] = value;
        any = true;
        continue;

      case 'studio':
        var studioId = getOrCreateStudio(value);
        if (studioId == null)
        {
          continue;
        }

        if (DEBUG)
        {
          bufferedOutput += field + ': ' + value + '\n';
          bufferedOutput += 'studio_id: ' + studioId + '\n';
        }

        variables.input['studio_id'] = studioId;
        any = true;
        continue;

      case 'movie_title':
        var movie_title = value.split(' ').join('[\\W]*');
        var movieId = tryGetMovie(movie_title);
        if (movieId == null)
        {
          continue;
        }

        if (!variables.input.hasOwnProperty('movies'))
        {
          variables.input['movies'] = [{}];
        }

        if (DEBUG)
        {
          bufferedOutput += field + ': ' + value + '\n';
          bufferedOutput += 'movie_id: ' + movieId + '\n';
        }

        variables.input['movies'][0]['movie_id'] = movieId;
        any = true;
        continue;

      case 'scene_index':
        var sceneIndex = parseInt(value);
        if (isNaN(sceneIndex))
        {
          continue;
        }

        if (!variables.input.hasOwnProperty('movies'))
        {
          variables.input['movies'] = [{}];
        }

        if (DEBUG)
        {
          bufferedOutput += 'scene_index: ' + sceneIndex + '\n';
        }

        variables.input['movies'][0]['scene_index'] = sceneIndex;
        continue;

      case 'performers':
        var performers = value.split(',').map(tryGetPerformer).filter(notNull);
        if (performers.length == 0)
        {
          continue;
        }

        if (DEBUG)
        {
          bufferedOutput += field + ': ' + value + '\n';
          bufferedOutput += 'performer_ids: ' + performers.join(', ') + '\n';
        }

        variables.input['performer_ids'] = performers;
        any = true;
        continue;

      case 'tags':
        var tags = value.split(',').map(getOrCreateTag).filter(notNull);
        if (tags.length == 0)
        {
          continue;
        }

        if (DEBUG)
        {
          bufferedOutput += field + ': ' + value + '\n';
          bufferedOutput += 'tag_ids: ' + tags.join(', ') + '\n';
        }

        variables.input['tag_ids'] = tags;
        any = true;
        continue;
      default:
        if (DEBUG)
        {
          bufferedOutput += field + ': ' + value + '\n';
        }
        variables.input[field] = value;
        any = true;
    }
  }

  // Test only
  if (DEBUG)
  {
    if (!any)
    {
      bufferedOutput += 'No fields to update!\n';
    }

    return;
  }

  // Remove movies if movie_id is missing
  if (variables.input.hasOwnProperty('movies') && !variables.input['movies'][0].hasOwnProperty('movie_id'))
  {
    delete variables.input['movies'];
  }

  // Apply updates
  var query = '\
  mutation Mutation($input: SceneUpdateInput!) {\
    sceneUpdate(input: $input) {\
      id\
    }\
  }';

  if (!any)
  {
    throw 'No fields to update for scene ' + sceneId;
  }

  var result = gql.Do(query, variables);
  if (result.sceneUpdate)
  {
    log.Info('[PathParser] Rule: ' + rule.name +
      '\nPath: ' + scenePath +
      '\nUpdated scene: ' + sceneId);
  }
  else
  {
    throw 'Unable to update scene ' + sceneId;
  }
}

// Returns true for not null elements
function notNull(ele)
{
  return ele != null;
}

// Get studio id from studio name
function tryGetStudio(studio)
{
  var query = '\
  query FindStudios($studioFilter: StudioFilterType) {\
    findStudios(studio_filter: $studioFilter) {\
      studios {\
        id\
      }\
      count\
    }\
  }';

  var variables = {
    studioFilter: {
      name: {
        value: studio.trim(),
        modifier: 'EQUALS'
      }
    }
  };

  var result = gql.Do(query, variables);
  if (!result.findStudios || result.findStudios.count == 0)
  {
    return;
  }

  return result.findStudios.studios[0].id;
}

function createStudio(studio)
{
  studio = studio.trim();
  if (!studio)
  {
    return null;
  }

  if (DEBUG)
  {
    bufferedOutput += 'studio: ' + studio + ' would be created' + '\n';
    return null;
  }

  log.Info('[PathParser] createStudio(' + studio + ')');
  var query = '\
  mutation StudioCreate($input: StudioCreateInput!) {\
    studioCreate(input: $input) {\
      id\
    }\
  }';

  var variables = {
    input: {
      name: studio
    }
  };

  var result = gql.Do(query, variables);
  if (!result.studioCreate)
  {
    throw 'Could not create studio ' + studio;
  }

  return result.studioCreate.id;
}

// Get studio id from studio name and create it if it doesn't exist
function getOrCreateStudio(studio)
{
  var studioId = tryGetStudio(studio);

  if (studioId)
  {
    return studioId;
  }

  return createStudio(studio);
}

function tryGetMovie(movie_title)
{
  var query = '\
  query FindMovies($movieFilter: MovieFilterType) {\
    findMovies(movie_filter: $movieFilter) {\
      movies {\
        id\
      }\
      count\
    }\
  }';

  var variables = {
    movieFilter: {
      name: {
        value: movie_title.trim(),
        modifier: 'MATCHES_REGEX'
      }
    }
  };

  var result = gql.Do(query, variables);
  if (!result.findMovies || result.findMovies.count == 0)
  {
    return;
  }

  return result.findMovies.movies[0].id;
}

function createPerformer(performer)
{
  performer = performer.trim();
  if (!performer)
  {
    return null;
  }

  if (DEBUG)
  {
    bufferedOutput += 'performers: ' + performer + ' would be created' + '\n';
    return null;
  }

  log.Info('[PathParser] createPerformer(' + performer + ')');
  var query = '\
  mutation PerformerCreate($input: PerformerCreateInput!) {\
    performerCreate(input: $input) {\
      id\
    }\
  }';

  var variables = {
    input: {
      name: performer
    }
  };

  var result = gql.Do(query, variables);
  if (!result.performerCreate)
  {
    throw 'Could not create performer ' + performer;
  }

  return result.performerCreate.id;
}


// Get performer id from performer name
function tryGetPerformer(performer)
{
  var query = '\
  query FindPerformers($performerFilter: PerformerFilterType) {\
    findPerformers(performer_filter: $performerFilter) {\
      performers {\
        id\
      }\
      count\
    }\
  }';

  performer = performer.trim();
  if (!performer)
  {
    return null;
  }

  var variables = {
    performerFilter: {
      name: {
        modifier: 'EQUALS',
        value: performer
      },
      OR: {
        aliases: {
          modifier: 'INCLUDES',
          value: performer
        }
      }
    }
  };

  var result = gql.Do(query, variables);
  if (!result.findPerformers)
  {
    return null;
  }

  if (result.findPerformers.count == 0)
  {
    return createPerformer(performer);
  }

  return result.findPerformers.performers[0].id;
}

// Get tag id from tag name
function tryGetTag(tag)
{
  var query = '\
  query FindTags($tagFilter: TagFilterType) {\
    findTags(tag_filter: $tagFilter) {\
      tags {\
        id\
      }\
      count\
    }\
  }';

  var variables = {
    tagFilter: {
      name: {
        value: tag.trim(),
        modifier: 'EQUALS'
      }
    }
  };

  var result = gql.Do(query, variables);
  if (!result.findTags || result.findTags.count == 0)
  {
    return null;
  }

  return result.findTags.tags[0].id;
}

// Get tag id from tag name and create it if it doesn't exist
function getOrCreateTag(tag)
{
  var tagId = tryGetTag(tag);

  if (tagId)
  {
    return tagId;
  }

  return createTags([tag]);
}

var DEBUG = false;
var BASE_PATHS = [];
var bufferedOutput = '';
main();
