from __future__ import print_function

import os
import subprocess


def check(file):
    # WARNING: this will break if the swagger-cli is not installed
    # npm install -g swagger-cli
    # see: https://www.npmjs.com/package/swagger-cli
    args = ["swagger", "validate", file]
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = p.communicate()
    if len(out) != 0:
        print(out)
        if len(err) != 0:
            print(err)
    return not len(err)


def test_swagger_files():
    current_dir = os.path.dirname(os.path.realpath(__file__))
    assert check(os.path.join(current_dir, "../apis/api.yaml")), 'api.yaml has errors'
    assert check(os.path.join(current_dir, "../apis/crawler.yaml")), 'crawler.yaml has errors'
