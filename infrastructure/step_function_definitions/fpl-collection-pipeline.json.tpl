{
  "Comment": "FPL data collection, validation, transformation, and enrichment pipeline",
  "StartAt": "CheckInputMode",
  "States": {
    "CheckInputMode": {
      "Type": "Choice",
      "Comment": "If gameweek is provided (backfill), skip resolution. Otherwise resolve from FPL API.",
      "Choices": [
        {
          "Variable": "$.gameweek",
          "NumericGreaterThan": 0,
          "Next": "CollectParallel"
        }
      ],
      "Default": "ResolveGameweek"
    },
    "ResolveGameweek": {
      "Type": "Task",
      "Resource": "${lambda_arn_resolve_gameweek}",
      "Parameters": {
        "season.$": "$.season",
        "last_processed_gw.$": "$.last_processed_gw",
        "force.$": "$.force"
      },
      "ResultPath": "$.resolved",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 10,
          "MaxAttempts": 2,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "PipelineFailed"
        }
      ],
      "Next": "CheckResolveStatus"
    },
    "CheckResolveStatus": {
      "Type": "Choice",
      "Comment": "Guard: route to PipelineFailed if the resolve Lambda returned a non-200 status",
      "Choices": [
        {
          "Variable": "$.resolved.statusCode",
          "NumericEquals": 200,
          "Next": "CheckShouldRun"
        }
      ],
      "Default": "PipelineFailed"
    },
    "CheckShouldRun": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.resolved.body.should_run",
          "BooleanEquals": false,
          "Next": "PipelineSkipped"
        }
      ],
      "Default": "PrepareResolvedInput"
    },
    "PrepareResolvedInput": {
      "Type": "Pass",
      "Comment": "Flatten resolved gameweek into top-level state for downstream steps",
      "Parameters": {
        "season.$": "$.resolved.body.season",
        "gameweek.$": "$.resolved.body.gameweek",
        "force.$": "$.resolved.body.force"
      },
      "Next": "CollectParallel"
    },

    "CollectParallel": {
      "Type": "Parallel",
      "Comment": "Collect from all 3 data sources in parallel — they are independent",
      "ResultPath": "$.collect_results",
      "Branches": [
        {
          "StartAt": "CollectFPLData",
          "States": {
            "CollectFPLData": {
              "Type": "Task",
              "Resource": "${lambda_arn_fpl_collector}",
              "Parameters": {
                "season.$": "$.season",
                "gameweek.$": "$.gameweek",
                "force.$": "$.force"
              },
              "TimeoutSeconds": 120,
              "Retry": [
                {
                  "ErrorEquals": ["States.TaskFailed"],
                  "IntervalSeconds": 30,
                  "MaxAttempts": 3,
                  "BackoffRate": 2.0
                }
              ],
              "End": true
            }
          }
        },
        {
          "StartAt": "CollectUnderstat",
          "States": {
            "CollectUnderstat": {
              "Type": "Task",
              "Resource": "${lambda_arn_understat_collector}",
              "Parameters": {
                "season.$": "$.season",
                "gameweek.$": "$.gameweek"
              },
              "TimeoutSeconds": 120,
              "Retry": [
                {
                  "ErrorEquals": ["States.TaskFailed"],
                  "IntervalSeconds": 60,
                  "MaxAttempts": 2,
                  "BackoffRate": 1.5
                }
              ],
              "End": true
            }
          }
        },
        {
          "StartAt": "CollectNews",
          "States": {
            "CollectNews": {
              "Type": "Task",
              "Resource": "${lambda_arn_news_collector}",
              "Parameters": {
                "season.$": "$.season",
                "gameweek.$": "$.gameweek"
              },
              "TimeoutSeconds": 120,
              "Retry": [
                {
                  "ErrorEquals": ["States.TaskFailed"],
                  "IntervalSeconds": 30,
                  "MaxAttempts": 2,
                  "BackoffRate": 2.0
                }
              ],
              "End": true
            }
          }
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "PipelineFailed"
        }
      ],
      "Next": "ValidateRawData"
    },

    "ValidateRawData": {
      "Type": "Task",
      "Resource": "${lambda_arn_validator}",
      "Parameters": {
        "season.$": "$.season",
        "gameweek.$": "$.gameweek"
      },
      "ResultPath": "$.validation",
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "PipelineFailed"
        }
      ],
      "Next": "CheckValidation"
    },
    "CheckValidation": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.validation.statusCode",
          "NumericEquals": 200,
          "Next": "CheckValidationResult"
        }
      ],
      "Default": "PipelineFailed"
    },
    "CheckValidationResult": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.validation.body.status",
          "StringEquals": "invalid",
          "Next": "PipelineFailed"
        }
      ],
      "Default": "TransformData"
    },

    "TransformData": {
      "Type": "Task",
      "Resource": "${lambda_arn_transform}",
      "Parameters": {
        "season.$": "$.season",
        "gameweek.$": "$.gameweek"
      },
      "ResultPath": "$.transform",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 30,
          "MaxAttempts": 2,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "PipelineFailed"
        }
      ],
      "Next": "CheckTransform"
    },
    "CheckTransform": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.transform.statusCode",
          "NumericEquals": 200,
          "Next": "EnrichParallel"
        }
      ],
      "Default": "PipelineFailed"
    },

    "EnrichParallel": {
      "Type": "Parallel",
      "Comment": "Run all 4 enrichers in parallel — each is an independent Lambda",
      "ResultPath": "$.enrichment_results",
      "Branches": [
        {
          "StartAt": "EnrichPlayerSummary",
          "States": {
            "EnrichPlayerSummary": {
              "Type": "Task",
              "Resource": "${lambda_arn_enrich_player_summary}",
              "Parameters": {
                "season.$": "$.season",
                "gameweek.$": "$.gameweek",
                "prompt_version": "v1"
              },
              "TimeoutSeconds": 900,
              "Retry": [
                {
                  "ErrorEquals": ["States.TaskFailed"],
                  "IntervalSeconds": 60,
                  "MaxAttempts": 2,
                  "BackoffRate": 2.0
                }
              ],
              "End": true
            }
          }
        },
        {
          "StartAt": "EnrichInjurySignal",
          "States": {
            "EnrichInjurySignal": {
              "Type": "Task",
              "Resource": "${lambda_arn_enrich_injury_signal}",
              "Parameters": {
                "season.$": "$.season",
                "gameweek.$": "$.gameweek",
                "prompt_version": "v1"
              },
              "TimeoutSeconds": 900,
              "Retry": [
                {
                  "ErrorEquals": ["States.TaskFailed"],
                  "IntervalSeconds": 60,
                  "MaxAttempts": 2,
                  "BackoffRate": 2.0
                }
              ],
              "End": true
            }
          }
        },
        {
          "StartAt": "EnrichSentiment",
          "States": {
            "EnrichSentiment": {
              "Type": "Task",
              "Resource": "${lambda_arn_enrich_sentiment}",
              "Parameters": {
                "season.$": "$.season",
                "gameweek.$": "$.gameweek",
                "prompt_version": "v1"
              },
              "TimeoutSeconds": 900,
              "Retry": [
                {
                  "ErrorEquals": ["States.TaskFailed"],
                  "IntervalSeconds": 60,
                  "MaxAttempts": 2,
                  "BackoffRate": 2.0
                }
              ],
              "End": true
            }
          }
        },
        {
          "StartAt": "EnrichFixtureOutlook",
          "States": {
            "EnrichFixtureOutlook": {
              "Type": "Task",
              "Resource": "${lambda_arn_enrich_fixture_outlook}",
              "Parameters": {
                "season.$": "$.season",
                "gameweek.$": "$.gameweek",
                "prompt_version": "v1"
              },
              "TimeoutSeconds": 900,
              "Retry": [
                {
                  "ErrorEquals": ["States.TaskFailed"],
                  "IntervalSeconds": 60,
                  "MaxAttempts": 2,
                  "BackoffRate": 2.0
                }
              ],
              "End": true
            }
          }
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "PipelineFailed"
        }
      ],
      "Next": "MergeEnrichments"
    },
    "MergeEnrichments": {
      "Type": "Task",
      "Resource": "${lambda_arn_merge_enrichments}",
      "Parameters": {
        "season.$": "$.season",
        "gameweek.$": "$.gameweek"
      },
      "ResultPath": "$.enrichment",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 10,
          "MaxAttempts": 1,
          "BackoffRate": 1.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "PipelineFailed"
        }
      ],
      "Next": "CheckEnrichment"
    },
    "CheckEnrichment": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.enrichment.statusCode",
          "NumericEquals": 200,
          "Next": "CurateData"
        }
      ],
      "Default": "PipelineFailed"
    },

    "CurateData": {
      "Type": "Task",
      "Resource": "${lambda_arn_curate_data}",
      "Parameters": {
        "season.$": "$.season",
        "gameweek.$": "$.gameweek"
      },
      "ResultPath": "$.curation",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 10,
          "MaxAttempts": 2,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "PipelineFailed"
        }
      ],
      "Next": "PipelineSucceeded"
    },

    "PipelineSucceeded": {
      "Type": "Succeed"
    },
    "PipelineSkipped": {
      "Type": "Succeed",
      "Comment": "No new gameweek to process — pipeline exits cleanly."
    },
    "PipelineFailed": {
      "Type": "Fail",
      "Error": "PipelineError",
      "Cause": "One or more pipeline steps failed — check CloudWatch logs for details."
    }
  }
}
