{
  "Comment": "FPL data collection, validation, transformation, and enrichment pipeline",
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
      "ResultPath": "$.collect_fpl",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 30,
          "MaxAttempts": 3,
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
      "Next": "CollectUnderstat"
    },
    "CollectUnderstat": {
      "Type": "Task",
      "Resource": "${lambda_arn_understat_collector}",
      "Parameters": {
        "season.$": "$.season",
        "gameweek.$": "$.gameweek"
      },
      "ResultPath": "$.collect_understat",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 60,
          "MaxAttempts": 2,
          "BackoffRate": 1.5
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "ResultPath": "$.error",
          "Next": "PipelineFailed"
        }
      ],
      "Next": "CollectNews"
    },
    "CollectNews": {
      "Type": "Task",
      "Resource": "${lambda_arn_news_collector}",
      "Parameters": {
        "season.$": "$.season",
        "gameweek.$": "$.gameweek"
      },
      "ResultPath": "$.collect_news",
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
          "Variable": "$.validation.body.records_invalid",
          "NumericGreaterThan": 0,
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
      "Next": "EnrichWithLLM"
    },
    "EnrichWithLLM": {
      "Type": "Task",
      "Resource": "${lambda_arn_enricher}",
      "Parameters": {
        "season.$": "$.season",
        "gameweek.$": "$.gameweek"
      },
      "ResultPath": "$.enrichment",
      "TimeoutSeconds": 600,
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 60,
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
      "Next": "PipelineSucceeded"
    },
    "PipelineSucceeded": {
      "Type": "Succeed"
    },
    "PipelineFailed": {
      "Type": "Fail",
      "Error": "PipelineError",
      "Cause": "One or more pipeline steps failed — check CloudWatch logs for details."
    }
  }
}