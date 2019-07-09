#!/bin/bash


set -e

ARGS=$@

ROOTDIR=$(git rev-parse --show-toplevel)
cd $ROOTDIR

if [ ! -e 'pym-config.yaml' ]; then
    echo "ERROR: no pym-config.yaml in current dir"
    exit 1
fi

NAME=$(pymconfig --name)

usage() {
    cat << EOF
USAGE: lambdadeploy [--debug]

Deploy BDL lambdas to amazon and setup their scheduler.

OPTIONS:

  --debug:          Be very verbose.
  --create:         Create the lambda functions, instead of just updating them.
  --test            Just test the lambdas.

USAGE:

./lambdadeploy

EOF
}

WITH_DEBUG=
DO_CREATE=
DO_UPDATE=1
DO_TEST=
TEST_PAYLOAD='NOP'

parse_args() {
    while [ "$1" != "" ]; do
        case $1 in
            "--debug")         set -x; DEBUG='true'; WITH_DEBUG="--debug";;
            "--create")        DO_CREATE=1; DO_UPDATE=;;
            "--test")          DO_TEST=1;;
            "--test-fail")     DO_TEST=1; TEST_PAYLOAD='FAIL';;
            "-h" | "--help")   usage; exit 0;;
            *)                 echo "Unknown argument '$1' (-h for help)"; exit 0;;
        esac
        shift
    done
}

parse_args $ARGS

AWS_PROFILE=$(pymconfig --aws-user)
AWS_REGION=$(pymconfig --aws-region)

# Prepare a tmp dir and clean it up
TMPDIR=/tmp/lambda-deploy
ZIPFILE=$TMPDIR/function.zip
mkdir -p $TMPDIR
# rm -rf $TMPDIR/venv
rm -f $ZIPFILE

echo "=> Root dir is $ROOTDIR"
echo "=> Tmp dir is $TMPDIR"

check_git_repo() {
    IS_DIRTY_CLONE=$(git status --short --porcelain | wc -l)
    if [ "$IS_DIRTY_CLONE" -gt 0 ]; then
        echo "ERROR: $PWD is not clean! Commit and re-run."
        exit 1
    fi

    GIT_DIFF_REMOTE=$(git diff master origin/master | wc -l)
    if [ "$GIT_DIFF_REMOTE" -ne 0 ]; then
        echo "ERROR: $PWD differs from origin. Please push to origin before releasing!"
        exit 1
    fi
}

create_virtenv() {
    echo "=> Generating dependencies archive"
    cd $TMPDIR
    virtualenv -p python3 $TMPDIR/venv
    source venv/bin/activate
    pip install -r $ROOTDIR/requirements.txt
    deactivate
}

build_zip() {
    cd $TMPDIR/venv/lib/python3.4/site-packages
    zip -r9 $ZIPFILE .
    cd $ROOTDIR
    zip -ur $ZIPFILE lambdas/*.py
    zip -ur $ZIPFILE bdl/
    zip -ur $ZIPFILE pym-config.yaml
}

# check_git_repo

# Compile environment variables into one string
SECRETS=""
for VAR in $(pymconfig --env-secrets)
do
    echo "=> Adding $VAR"
    VALUE=$(env | grep "^$VAR=" | cut -d '=' -f 2)
    if [ -z "$VALUE" ]; then
        echo "ERROR: variable $VAR has no value in env"
        exit 1
    fi
    SECRETS="$VAR=$VALUE,$SECRETS"
    echo "ESCRETS IS NOW [$SECRETS]"
done
SECRETS=$(echo $SECRETS | sed -e "s|,$||")

echo "=> SECRETS=$SECRETS"

# Invoke a lambda to test it
test_lambda() {
    LAMBDA_NAME=$1

    # Test that the function was properly created and runs fine
    echo "=> Invoking $LAMBDA_NAME in self-test mode"
    aws lambda invoke \
        --profile $AWS_PROFILE \
        --function-name $LAMBDA_NAME \
        --invocation-type RequestResponse \
        --payload '{"action": "'$TEST_PAYLOAD'"}' \
        outfile

    OK=$(cat outfile | grep '"statusCode": 200' | wc -l)
    rm outfile
    if [ $OK -ne 1 ]; then
        echo "ERROR: self-test of $LAMBDA_NAME failed!"
        exit 1
    else
        echo "=> Test successful!"
    fi
}


# Create each lambda function
create_lambda() {
    LAMBDA_NAME=$1
    METHOD_NAME=$2
    cd $TMPDIR

    # Delete the function if it already exists
    echo "=> Checking if function $LAMBDA_NAME exists"
    set +e
    eval aws lambda get-function \
         --region $AWS_REGION \
         --profile $AWS_PROFILE \
         --function-name $LAMBDA_NAME 2> /dev/null
    RC=$?
    set -e
    if [ $RC == 0 ]; then
        echo "=> Function $LAMBDA_NAME already exists. Deleting it first"
        aws lambda delete-function \
            --region $AWS_REGION \
            --profile $AWS_PROFILE \
            --function-name $LAMBDA_NAME
    else
        echo "=> Function $LAMBDA_NAME does not exist yet"
    fi

    # Create the function
    echo "=> Creating lambda $LAMBDA_NAME"
    aws lambda create-function \
        --function-name $LAMBDA_NAME \
        --region $AWS_REGION \
        --zip-file fileb://function.zip \
        --handler lambdas.lambdas.$METHOD_NAME \
        --runtime python3.7 \
        --role arn:aws:iam::579726532991:role/PymacaronLambda \
        --tracing-config Mode=Active \
        --timeout 300 \
        --environment Variables="{$SECRETS}" \
        --profile $AWS_PROFILE

    # And make sure it's working
    test_lambda $LAMBDA_NAME
}

update_lambda() {
    LAMBDA_NAME=$1
    cd $TMPDIR

    # Stop if function does not exist
    echo "=> Checking if function $LAMBDA_NAME exists"
    eval aws lambda get-function \
         --region $AWS_REGION \
         --profile $AWS_PROFILE \
         --function-name $LAMBDA_NAME

    # Update the function's code
    echo "=> Updating lambda $LAMBDA_NAME"
    aws lambda update-function-code \
        --region $AWS_REGION \
        --function-name $LAMBDA_NAME \
        --zip-file fileb://function.zip \
        --profile $AWS_PROFILE

    # And update its configuration
    aws lambda update-function-configuration \
        --region $AWS_REGION \
        --function-name $LAMBDA_NAME \
        --handler lambdas.lambdas.$METHOD_NAME \
        --runtime python3.7 \
        --role arn:aws:iam::579726532991:role/PymacaronLambda \
        --tracing-config Mode=Active \
        --timeout 300 \
        --environment Variables="{$SECRETS}" \
        --profile $AWS_PROFILE
}

if [ ! -z "$DO_TEST" ]; then
    test_lambda update_sitemap
    test_lambda scan_source

else

    create_virtenv
    build_zip

    if [ ! -z "$DO_CREATE" ]; then
        create_lambda update_sitemap lambda_update_sitemap
        create_lambda scan_source lambda_scan_source
        # create_lambda clean_source lambda_clean_source

    elif [ ! -z "$DO_UPDATE" ]; then
        update_lambda update_sitemap
        create_lambda scan_source

    fi
fi

echo "=> Done."
