"""Submits an exercise to CodeOcean for evaluation" 
   by wrglprmft """

import json
import http
import urllib.error
import urllib.request
import os
import textwrap
import argparse

VERSION = "0.1.4"


def submit_and_pray(exercise_directory=".", stderr=True, stdout=True):
    """
    main entry point:
    needs a directory, that contains the .co file (and sources to be submitted)
    submits and prints result from codeocean and also stderr/stdout from
    the codeocean response if wanted
    """
    print(f"CodeOcean Remote Client v{VERSION} (by wrglprmft)")
    try:
        if not os.path.isdir(exercise_directory):
            print(f"{exercise_directory} is not a directory")
            return

        # response has status, headers and binary content
        print("--- Submit")
        response = submit(exercise_directory)

        # result is a list of dictionaries
        result = check_response(response)
        print("|\n| Files submitted:", get_header(response["headers"], "location"))

        print_result(result, stderr, stdout)

    except FileNotFoundError as fnfe:
        # raised if .co file or required src files are not in the
        # current directory
        print(f'File "{fnfe.filename}" not found')

    except AssertionError as ae:
        # raised if
        # o response code from the POST is not 201 (Created)
        #   but between 200 and 299
        # o headers don't contain a Content-Type with value
        #   "application/json"
        # o parsed response json does not have the expected structure:
        #   list of dicts containg "filename"
        print_error_response(ae.args[0])

    except urllib.error.URLError as ue:
        # raised if e.g. a network error occurs
        print(f"Generic exception: {str(ue)}")


def submit(project_directory):
    """
    builds payload from directory and submits it.
    returns a dictionary with status, headers and content
    """

    url, payload = create_payload(project_directory)
    return post_payload_as_json(url, payload)


def print_result(result, stderr=False, stdout=False):
    """
    prints the returned result
    result is a list of dictionaries
    """
    passed = 0
    count = 0
    max_cops = 0.0  # CodeOcean Points
    total_cops = 0.0

    # expect a list of dicts, matching the expected response structure
    scores = []
    for file in result:
        cops = file["score"] * file["weight"]  # CodeOcean Points
        scores.append((file["passed"], file["count"], cops, file["status"], file["weight"]))
        passed += file["passed"]
        count += file["count"]
        max_cops += file["weight"]
        total_cops += cops

        print(f"\n--- ({len(scores)}) {file['filename']}")
        if stdout:
            print_lines(file, "stdout")
        if stderr:
            print_lines(file, "stderr")
        print_error_messages(file.get("error_messages", None))
        print_lines(file, "message")

    cnt = 1
    percent = 100 if max_cops == 0 else round(100 * total_cops / max_cops, 2)
    total_cops = round(total_cops, 2)
    total_len = 58
    width = int(total_len * percent / 100)

    print("\n--- Total (points are CodeOcean points) ---")
    print(f"[{width*'#'}{(total_len-width)*'-'}] {percent:g}%")
    for score in scores:
        print(f"({cnt}) ==> passed {score[0]} / {score[1]} tests, ", end="")
        print(f"points = {round(score[2],2)} / {score[4]}, status = {score[3]}")
        cnt += 1
    print(f"\n    ==> passed {passed} / {count} tests, ", end="")
    print(f"points = {total_cops} / {max_cops}")


def print_error_messages(errors):
    """helper function"""
    if errors:
        print("|-- error_messages ---")
        for error in errors:
            for line in error.splitlines():
                print_long_line(line)
            print("|")


def print_lines(file, part):
    """helper function"""
    if file.get(part, None):
        print(f"|-- {part} ---")
    for line in file[part].splitlines():
        print_long_line(line)


def print_long_line(long_line):
    """helper function"""
    if long_line.strip() == "":
        print("|")
    else:
        for line in textwrap.wrap(long_line, 70):
            print("|", line)


def create_payload(directory):
    """
    creates the payload for the given directory
    reads .co file and the listed files
    returns an utf-8 encoded json string as bytes
    """
    # read control file with target url, validation token
    # and expected files
    co_file = read_utf8_file(directory, ".co").splitlines()

    # fill files_attributes
    files_attributes = {}
    for i in range(2, len(co_file)):
        file_name, file_id = co_file[i].split("=")
        print("|", file_name)
        files_attributes[str(i - 2)] = {
            "file_id": int(file_id),
            "content": read_utf8_file(directory, file_name),
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
    """posts the given payload to the given url as application/json"""
    request = urllib.request.Request(url, payload, {"Content-Type": "application/json"})
    response = {}
    try:
        with urllib.request.urlopen(request) as http_response:
            response = {
                "content": http_response.read(),
                "headers": http_response.getheaders(),
                "status": http_response.status,
            }
    except urllib.error.HTTPError as he:
        # raised if the response code from the POST request is not 2xx
        response = {"content": he.fp.read(), "headers": he.headers.items(), "status": he.code}

    return response


def read_utf8_file(directory, file_name):
    """reads a file assuming it'S utf-8 encoded. returns a string"""
    with open(os.path.join(directory, file_name), encoding="utf-8") as file:
        content = file.read()
    return content


def check_response(response):
    """
    checks whether the response can be processed further
    only proceed if response is 201 (created) and a json
    """
    assert response["status"] == http.HTTPStatus.CREATED, response
    is_json = get_header(response["headers"], "content-type").startswith("application/json")
    assert is_json, response
    result = json.loads(response["content"])
    assert isinstance(result, list), response
    if len(result) > 0:  # There are tests"
        assert isinstance(result[0], dict), response
        assert "filename" in result[0], response

    return result


def print_error_response(response):
    """prints status, headers, code of an unprocessable response"""
    print("\n--- Unexpected response from server (CodeOcean) ---")
    status = response["status"]
    print(f"Http-Status:{status} ({http.HTTPStatus(status).phrase})")
    if get_header(response["headers"], "content-type").startswith("application/json"):
        body = json.loads(response["content"])
        if isinstance(body, dict):
            print(body.get("message"), "")

    if status == http.HTTPStatus.SERVICE_UNAVAILABLE:
        print("\nMost likely no execution environment is currently available.")
        print("Try again later.")
        return

    if status == http.HTTPStatus.UNPROCESSABLE_ENTITY:
        print("\nThe server cannot process the payload. This is an error.")
        print("in the script. Please report.")
        return

    print("\n----- Http-Headers:")
    for header in response["headers"]:
        print(header[0], ":", header[1])

    print("\n----- Content (utf-8 decoded):")
    print(response["content"].decode())


def get_header(headers, name):
    """gets a header from heades. name must be lower-case"""
    for header in headers:
        if header[0].lower() == name:
            return header[1]
    return ""


def main():
    """static main method called if script is not imported"""
    parser = argparse.ArgumentParser(
        description="Submits an exercise to CodeOcean for evaluation",
        epilog=20 * ". " + "(wrglprmft)",
    )
    parser.add_argument("directory", help="directory with .co file", default=".", nargs="?")
    parser.add_argument("-o", "--stdout", action="store_true", help="output also stdout")
    parser.add_argument("-e", "--stderr", action="store_true", help="output also stderr")
    parser.add_argument("--version", action="store_true", help="show version and exit")
    parameter = parser.parse_args()

    if parameter.version:
        print(f"Version {VERSION}")
        return

    submit_and_pray(parameter.directory, parameter.stderr, parameter.stdout)


# don't run while being imported
if __name__ == "__main__":
    main()
