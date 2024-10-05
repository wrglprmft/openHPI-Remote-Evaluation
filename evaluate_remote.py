import json
import http
import urllib.error
import urllib.request
import sys
import os


def main():
    try:
        # remember current directory and change directory as requested
        cwd = os.getcwd()
        if len(sys.argv) > 1:
            os.chdir(sys.argv[1])

        result = get_result()
        print_result(result)

    except FileNotFoundError as fnfe:
        # raised if .co file or required src files are not in the
        # current directory
        print(f'File/Directory "{fnfe.filename}" not found in {os.getcwd()}')

    except urllib.error.HTTPError as he:
        # raised if the response code from the POST request is
        # not 2xx (expected is 201)
        print_error_response(
            {
                "content": he.fp.read(),
                "headers": he.headers.items(),
                "status": he.code,
            }
        )

    except AssertionError as ae:
        # raised if
        # o response code from the POST is not 201 (Created)
        #   but between 200 and 299
        # o headers don't contain a Content-Type with value
        #   "application/json"
        # o parsed response json does not have the expected structure:
        #   non empty list of dicts containg "filename"
        print_error_response(ae.args[0])

    finally:
        os.chdir(cwd)


def get_result():
    url, payload = create_payload()
    response = post_payload_as_json(url, payload)
    return check_response(response)


def print_result(result):
    passed = 0
    count = 0
    weight = 0.0
    weighted_score = 0.0

    # expect a list of dicts, matching the expected response structure
    for file in result:
        passed += file["passed"]
        count += file["count"]
        weight += file["weight"]
        weighted_score += file["score"] * file["weight"]

        print(f"\n--- {file['filename']}")
        for error in file["error_messages"]:
            print(error)
        print(file["message"])
        print(f"==> passed {file['passed']} from {file['count']} tests, ", end="")
        print(f"score = {file['score']}, status = {file['status']}")

    print("\n--- Total ---")
    print(f"==> passed {passed} from {count} tests, ", end="")
    print(f"weighted score = {weighted_score/weight}")


def create_payload():
    # read control file with target url, validation token
    # and expected files
    co_file = read_utf8_file(".co").splitlines()

    # fill files_attributes
    files_attributes = {}
    for i in range(2, len(co_file)):
        file_name, file_id = co_file[i].split("=")
        files_attributes[str(i - 2)] = {
            "file_id": int(file_id),
            "content": read_utf8_file(file_name),
        }

    # UTF-8 (allowing non-ascii) and prefer a small json, i.e. no
    # spaces arround separators
    payload = json.dumps(
        {
            "remote_evaluation": {
                "validation_token": co_file[0],
                "files_attributes": files_attributes,
            }
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()

    return co_file[1], payload


def post_payload_as_json(url, payload):
    request = urllib.request.Request(url, payload, {"Content-Type": "application/json"})
    response = {}
    with urllib.request.urlopen(request) as http_response:
        response = {
            "content": http_response.read(),
            "headers": http_response.getheaders(),
            "status": http_response.status,
        }
    return response


def read_utf8_file(file_name):
    with open(file_name, encoding="utf-8") as file:
        content = file.read()
    return content


def check_response(response):
    # only proceed if response is ok (created) and a json
    assert response["status"] == http.HTTPStatus.CREATED, response
    found = False
    for header in response["headers"]:
        if header[0].lower() == "content-type" and "application/json" in header[1]:
            found = True
            break
    assert found, response
    result = json.loads(response["content"])
    assert isinstance(result, list), response
    assert len(result) > 0, response
    assert isinstance(result[0], dict), response
    assert "filename" in result[0], response

    return result


def print_error_response(response):
    print("*** Unexpected response from server (codeocean) ***")
    print(
        "Http Status Code:",
        response["status"],
        "(" + http.HTTPStatus(response["status"]).description + ")",
    )

    print("\n----- Http-Headers:")
    for header in response["headers"]:
        print("  ", header[0], ":", header[1])
        
    print("\n----- Content (utf-8 decoded):")
    print(response["content"].decode())


# don't run while being imported
if __name__ == "__main__":
    main()
