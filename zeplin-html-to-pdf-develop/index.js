process.env.PATH = process.env.PATH + ":" + process.env.LAMBDA_TASK_ROOT;

let wkhtmltopdf = require("./utils/wkhtmltopdf");
let errorUtil = require("./utils/error");
let AWS = require('aws-sdk');

function putObjectToS3(bucket, key, data, callback){
    let s3 = new AWS.S3();
    let params = {
        Bucket: bucket,
        Key: key,
        Body: data
    };
//    s3.putObject(params, function(err, data){
//        if (err) {
//            console.log(err, err.stack)
//            errorUtil.createErrorResponse(500, "Internal server error", err)
//        }
//        else {
//            callback(null, "Uploaded object successfully");
//        }
//    });
}

function valiadateParams(event) {
    let errors = false;
    let fields = ['html', 'bucket', 'key'];
    let eventKeys = Object.keys(event);
    let missingKeys = fields.filter(key => !(key in eventKeys));

    if (missingKeys.length > 0) {
        let errorResponse = errorUtil.createErrorResponse(
            400,
            `Validation error: Missing field(s) ${missingKeys.join(", ")}.`
        );
        callback(errorResponse);
        errors = true;
    }
    return errors;
}

exports.handler = function handler(event, context, callback) {
    if (!valiadateParams(event)) {
        return;
    }

    wkhtmltopdf(event.html)
        .then(function (buffer) {
            putObjectToS3(bucket, key, data, callback)
        }).catch(function (error) {
            callback(errorUtil.createErrorResponse(500, "Internal server error", error));
        });
};
