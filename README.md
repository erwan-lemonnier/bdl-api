# The BDL (Bazardelux) API


### Architecture

For an architectural overview of how the BDL API and SCRAPER interact, see
[here](https://github.com/erwan-lemonnier/bdl-api/blob/master/architecture-1.png).


### Testing API and SCRAPER locally

(WARNING: NOT IMPLEMENTED YET!!!)

The API and SCRAPER microservices send requests to each other. Both services
must therefore be running to get a standalone test environment. By default,
each calls the live host:port for the other, as specified in the swagger files.

Those host:port can be overriden by setting the environment variables
BDL_API_HOST and BDL_SCRAPER_HOST.

To run both services beside each other on your dev laptop, start 2 terminals and
do in each:

```shell
# Shell running the BDL API
cd bdl-api
export BDL_SCRAPER_HOST=127.0.0.1:8888
python server.py --port 8080
```

```shell
# Shell running the BDL SCRAPER
cd bdl-api
export BDL_API_HOST=127.0.0.1:8080
python server.py --port 8888
```
