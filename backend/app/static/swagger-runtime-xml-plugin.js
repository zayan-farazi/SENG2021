/* runtime-xml-example-plugin */
(function () {
  function getRawXmlExample(schema, example) {
    var candidates = [example, schema && schema.example];
    for (var i = 0; i < candidates.length; i += 1) {
      var candidate = candidates[i];
      if (typeof candidate === "string" && candidate.trimStart().startsWith("<?xml")) {
        return candidate;
      }
    }
    return null;
  }

  window.RuntimeXmlExamplePlugin = function RuntimeXmlExamplePlugin(system) {
    var jsonSchemaFns = (system && system.fn && system.fn.jsonSchema202012) || {};
    var defaultGetXmlSampleSchema = jsonSchemaFns.getXmlSampleSchema
      ? jsonSchemaFns.getXmlSampleSchema.bind(jsonSchemaFns)
      : null;
    var defaultGetSampleSchema = jsonSchemaFns.getSampleSchema
      ? jsonSchemaFns.getSampleSchema.bind(jsonSchemaFns)
      : null;

    return {
      fn: {
        jsonSchema202012: {
          getXmlSampleSchema: function getXmlSampleSchema(schema, config, example) {
            var rawXmlExample = getRawXmlExample(schema, example);
            if (rawXmlExample) {
              return rawXmlExample;
            }
            if (defaultGetXmlSampleSchema) {
              return defaultGetXmlSampleSchema(schema, config, example);
            }
            return "";
          },
          getSampleSchema: function getSampleSchema(schema, contentType, config, example) {
            var rawXmlExample =
              /xml/i.test(contentType || "") && getRawXmlExample(schema, example);
            if (rawXmlExample) {
              return rawXmlExample;
            }
            if (defaultGetSampleSchema) {
              return defaultGetSampleSchema(schema, contentType, config, example);
            }
            if (defaultGetXmlSampleSchema && /xml/i.test(contentType || "")) {
              return defaultGetXmlSampleSchema(schema, config, example);
            }
            return example;
          },
        },
      },
    };
  };
})();
