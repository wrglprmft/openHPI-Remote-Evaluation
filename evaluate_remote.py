import json
import http
import urllib.error
import urllib.request
import sys
import os
import datetime

global_project_directory = "."


def main(project_dir = "."):
    try:
        if not os.path.isdir(project_dir):
            print(f"{project_dir} is not a directory")
            return
        
        global global_project_directory
        global_project_directory = project_dir

        result = submit()
        print_result(result)

    except FileNotFoundError as fnfe:
        # raised if .co file or required src files are not in the
        # current directory
        print(f'File "{fnfe.filename}" not found')

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
        if isinstance(ae.args[0], str):
            # empty list (happens on Spielwiese)
            print(ae.args[0])
        else:    
            print_error_response(ae.args[0])


def submit():
    url, payload = create_payload()
    return post_payload_as_json(url, payload)


def print_result(response):
    result = check_response(response)
    save(response["content"])
    passed = 0
    count = 0
    weight = 0.0
    weighted_score = 0.0

    # expect a list of dicts, matching the expected response structure
    scores = []
    for file in result:
        scores.append((file["passed"], file["count"], file["score"], file["status"]))
        passed += file["passed"]
        count += file["count"]
        weight += file["weight"]
        weighted_score += file["score"] * file["weight"]

        print(f"\n--- {file['filename']}")
        # print_lines(file,"stdout")
        # print_lines(file,"stderr")
        print_error_messages(file["error_messages"])
        print_lines(file, "message")

    print("\n--- Total ---")
    cnt = 1
    if weight == 0:
        weight = 1
    for score in scores:
        print(f"({cnt}) ==> passed {score[0]} from {score[1]} tests, ", end="")
        print(f"score = {round(score[2],2)}, status = {score[3]}")
        cnt += 1
    print(f"==> passed {passed} from {count} tests, ", end="")
    print(f"total score = {weighted_score/weight}")


def print_error_messages(errors):
    if errors:
        print("|-- error_messages ---")
        for error in errors:
            for line in error.splitlines():
                print("|", line)
            print("|")


def print_lines(file, part):
    if file[part]:
        print(f"|-- {part} ---")
    for line in file[part].splitlines():
        print("|", line)


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
    with open(
        os.path.join(global_project_directory, file_name), encoding="utf-8"
    ) as file:
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
    assert len(result) > 0, "Files submitted, but there are no tests"
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


def save(result):
    if not os.path.exists("log") or not os.path.isdir("log"):
        return

    fname = (
        "log/result_" + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S") + ".json"
    )
    with open(fname, "wb") as file:
        file.write(result)


# don't run while being imported
if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
