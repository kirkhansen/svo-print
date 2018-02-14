process.env.PATH = process.env.PATH + ":" + process.env.LAMBDA_TASK_ROOT;

let wkhtmltopdf = require("./utils/wkhtmltopdf");
let errorUtil = require("./utils/error");
let AWS = require('aws-sdk');

function putObjectToS3(event, buffer, callback){
    let s3 = new AWS.S3();
    let params = {
        Bucket: event.bucket,
        Key: event.key,
        Body: buffer.toString("base64")
    };
    s3.putObject(params, function(err, data){
        if (err) {
            console.error(err, err.stack);
            errorUtil.createErrorResponse(500, "Internal server error", err);
        }
        else {
            callback(null, {data: buffer.toString("base64")});
        }
    });
}

function validateParams(event, callback) {
    let valid = true;
    let fields = ['html', 'bucket', 'key'];
    let missingKeys = fields.filter(key => !(key in event));
    if (missingKeys.length > 0) {
        let errorResponse = errorUtil.createErrorResponse(
            400,
            `Validation error: Missing field(s) ${missingKeys.join(", ")}.`
        );
        console.error(errorResponse)
        callback(errorResponse);
        valid = false;
    }
    return valid;
}

exports.handler = function handler(event, context, callback) {
    if (validateParams(event, callback) === false) {
        return;
    }
    wkhtmltopdf(event.html)
        .then(function (buffer) {
            putObjectToS3(event, buffer, callback)
        }).catch(function (error) {
            callback(errorUtil.createErrorResponse(500, "Internal server error", error));
            console.error(error);
        });
};
