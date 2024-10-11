import json
import http
import urllib.error
import urllib.request
import sys
import os
import datetime
import textwrap


# main entry point:
# needs a directory, that contains the .co file (and sources to be submitted)
# submits and prints result from codeocean and also stderr/stdout from
# the codeocean response if wanted
def submit_and_pray(exercise_directory=".", stderr=True, stdout=True):
    try:
        if not os.path.isdir(exercise_directory):
            print(f"{exercise_directory} is not a directory")
            return

        # response has status, headers and binary content
        response = submit(exercise_directory)

        # result is a list of dictionaries
        result = check_response(response)
        print(f"|\n| Files submitted:", get_location_header(response["headers"]))

        # save the valid (binary) content if a directory "./log" exists
        save(response["content"])

        print_result(result, stderr, stdout)

    except FileNotFoundError as fnfe:
        # raised if .co file or required src files are not in the
        # current directory
        print(f'File "{fnfe.filename}" not found')

    except urllib.error.HTTPError as he:
        # raised if the response code from the POST request is
        # not 2xx (expected is 201)
        if he.code == http.HTTPStatus.SERVICE_UNAVAILABLE:
            print(http.HTTPStatus.SERVICE_UNAVAILABLE.description)
            print("\nMost likely no execution environment is currently available")
            print("Try again later")
            return
        
        if he.code == http.HTTPStatus.UNPROCESSABLE_ENTITY:
             print(http.HTTPStatus.SERVICE_UNAVAILABLE.description)
             print("\n Ohoh")
             print("The server cannot process the payload. This is an error")
             print("in the script. Please report")
             return
        
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


def submit(project_directory):
    url, payload = create_payload(project_directory)
    return post_payload_as_json(url, payload)


def print_result(result, stderr, stdout):

    passed = 0
    count = 0
    total_weight = 0.0
    total_cops = 0.0  # CodeOcean Points

    # expect a list of dicts, matching the expected response structure
    scores = []
    file_counter = 1
    for file in result:
        cops = file["score"] * file["weight"]  # CodeOcean Points
        scores.append(
            (
                file["passed"],
                file["count"],
                cops,
                file["status"],
            )
        )
        passed += file["passed"]
        count += file["count"]
        total_weight += file["weight"]
        total_cops += cops

        print(f"\n--- ({file_counter}) {file['filename']}")
        if stdout:
            print_lines(file, "stdout")
        if stderr:
            print_lines(file, "stderr")
        print_error_messages(file.get("error_messages", None))
        print_lines(file, "message")

        file_counter += 1

    print("\n--- Total (points are CodeOcean points; openHPI points might differ) ---")
    cnt = 1
    if total_weight == 0:
        percent = 100
    else:
        percent = round(100 * total_cops / total_weight, 2)
    total_cops = {round(total_cops,2)}    

    for score in scores:
        print(f"({cnt}) ==> passed {score[0]} from {score[1]} tests, ", end="")
        print(f"points = {round(score[2],2)}, status = {score[3]}")
        cnt += 1
    print(f"\n======> passed {passed} from {count} tests, ", end="")
    print(
        f"total points = {total_cops} ({percent:g}%) <=====",
    )


def print_error_messages(errors):
    if errors:
        print("|-- error_messages ---")
        for error in errors:
            for line in error.splitlines():
                print_long_line(line)
            print("|")


def print_lines(file, part):
    if file.get(part, None):
        print(f"|-- {part} ---")
    for line in file[part].splitlines():
        print_long_line(line)


def print_long_line(long_line):
    for line in textwrap.wrap(long_line, 76):
        print("|", line)


def create_payload(project_directory):
    # read control file with target url, validation token
    # and expected files
    co_file = read_utf8_file(project_directory, ".co").splitlines()

    # fill files_attributes
    files_attributes = {}
    print("--- Submit")
    for i in range(2, len(co_file)):
        file_name, file_id = co_file[i].split("=")
        print("|", file_name)
        files_attributes[str(i - 2)] = {
            "file_id": int(file_id),
            "content": read_utf8_file(project_directory, file_name),
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


def read_utf8_file(directory, file_name):
    with open(os.path.join(directory, file_name), encoding="utf-8") as file:
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
    if len(result) > 0:  # There are tests"
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

def get_location_header(headers):
    for header in headers:
        if header[0].lower() == "location":
            return header[1]
    return "no submission url availabale"        
        

def run(argv):
    exercise_directory = "."
    stderr = False
    stdout = False

    for i in range(1, len(argv)):
        if argv[i][0] != "-":
            exercise_directory = argv[i]
        elif argv[i] == "-o":
            stdout = True
        elif argv[i] == "-e":
            stderr = True
        else:
            print(f"\nUSAGE: {argv[0]} [-e] [-s] <directory>")
            print(f"  directory: directory containing the .co file")
            print(f"  -e: print also stderr from response")
            print(f"  -o: print also stdout from response")
            return

    submit_and_pray(exercise_directory, stderr, stdout)


# don't run while being imported
if __name__ == "__main__":
    run(sys.argv)
