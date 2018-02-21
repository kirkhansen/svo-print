# zeplin-html-to-pdf
Shamelessly stolen from the zeplin-html-to-pdf with some minor mods.

This is an AWS Lambda function that converts HTML pages to PDF documents using wkhtmltopdf.

It implements a simple interface to read and HTML input and output PDF content:

### Input
Input event to this function has the following structure: 
```
{
    "html": "<!DOCTYPE html><html><head><title>HTML doc</title></head><body>Content<body></html>",
    "bucket": "svo-print",
    "key": "test-svo-print-store/test.pdf"
}
```

### Output
This will save a pdf of the html to the specified bucket and key, and will also return
a `data` key containing the base64 encoded version of the pdf.
It yields a response in the following format: 
```
{
  "data": "JVBERi0xLjQKMSAwIG9iago8PAovVGl0bGUgKP7..."
}
```
`data` is base64 encoding of the converted PDF file.

### Test in local environment
The function can be tested locally running `npm test` command. It requires input file name, which should be an existing HTML file and output file name for the generated PDF document. Example:
```
$ npm test -- test.html test.pdf
```
