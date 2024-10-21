"""Submits an exercise to CodeOcean for evaluation" 

    An exercise downloaded as zip from CodeOcean should be extracted to
    a single directory <directory_name>

    This script takes this directory name and sends by interpreting the
    .co file the sources to CodeOcean. CodeOcean saves the sources,
    executes tests and returns the result(score) as json.

    The returned result is then parsed and printed. The result also contains
    stderr and stdout from the unit test run in CodeOcean. This is only
    output if requested.

   by wrglprmft """

import json
import http
import urllib.error
import urllib.request
import os
import textwrap
import argparse
import dataclasses

_VERSION = "0.1.7"

_COLS = 80
_BAR_WIDTH = _COLS - 10
_C_VERT = "\u2503"
_C_HOR = "\u2501"
_C_UL = "\u250F"
_C_UR = "\u2513"
_C_BL = "\u2517"
_C_BR = "\u251b"
_C_LEFT = "\u2523"
_C_RIGHT = "\u252b"


@dataclasses.dataclass
class Response:
    """Used as container to hold content, headers and status of an HTTP-Response"""

    content: bytes
    headers: object
    status: int


def evaluate(directory_name: str = ".", stderr: bool = False, stdout: bool = False) -> None:
    """submits the sources to CodeOcean and prints the results

    Args:
        directory_name (str, optional): directory containing the .co file. Defaults to ".".
        stderr (bool, optional): print also the stderr output of the result. Defaults to True.
        stdout (bool, optional): print also the stdout output of the result. Defaults to True.
    """
    top_out("")
    out(f" CodeOcean Remote Client v{_VERSION} (by wrglprmft)")
    out(f" {os.path.basename(os.path.abspath(directory_name))}")
    bottom_out()
    try:
        if not os.path.isdir(directory_name):
            print(f"{directory_name} is not a directory")
            return

        # response has status, headers and binary content
        top_out("Submit")
        response = submit(directory_name)

        # result is a list of dictionaries
        result = check_response(response)
        out("")
        out(" Submission created: " + get_header(response.headers, "location"))
        bottom_out()

        print_result(result, stderr, stdout)

    except FileNotFoundError as fnfe:
        # raised if .co file or required source files are not in the
        # current directory
        print(f'File "{fnfe.filename}" not found')

    except AssertionError as ae:
        # raised if
        # o response code from the POST is not 201 (Created)
        # o headers don't contain a Content-Type with value
        #   "application/json"
        # o parsed response json does not have the expected structure:
        #   list of dicts containg "filename"
        print_error_response(ae.args[0])

    except urllib.error.URLError as ue:
        # raised if e.g. a network error occurs
        print(f"Generic exception: {str(ue)}")


def submit(project_directory: str) -> Response:
    """builds payload files in directory and submits it

    Args:
        project_directory (str): directory containing .co file and sources

    Returns:
        Response: content, headers, status of the http response
    """

    url, payload = create_payload(project_directory)
    return post_payload_as_json(url, payload)


def print_result(result: list, stderr: bool = False, stdout: bool = False) -> None:
    """_summary_

    Args:
        result (list): the result as list of dictionaries
        stderr (bool, optional): print also stderr. Defaults to False.
        stdout (bool, optional): print also stdout. Defaults to False.
    """
    passed, count, max_points, total_points = 0, 0, 0.0, 0.0

    # expect a list of dicts, matching the expected response structure
    for cnt, file in enumerate(result):
        passed += file["passed"]
        count += file["count"]
        max_points += file["weight"]
        total_points += file["score"] * file["weight"]  # CodeOcean Points

        top_out(f"({cnt+1}) {file['filename']}", 4)
        if stdout:
            print_lines(file, "stdout")
        if stderr:
            print_lines(file, "stderr")
        print_error_messages(file.get("error_messages", None))
        print_lines(file, "message")
        bottom_out()
    percent = 100 if max_points == 0 else round(100 * total_points / max_points, 2)
    width = int(_BAR_WIDTH * percent / 100)
    print(f"\n {width*'\u2593'}{(_BAR_WIDTH-width)*'\u2591'} {percent:g}%\n")

    for cnt, file in enumerate(result):
        print(f"  ({cnt+1}) ==> passed {file['passed']:2d} / {file['count']:2d} tests, ", end="")
        print(f"points = {round((file['score'] * file['weight']),2):5.2f} ", end="")
        print(f"/ {file['weight']:5.2f} ", end="")
        print(f", status = {file['status']}")

    print(f"          passed {passed:2d} / {count:2d} tests, ", end="")
    print(f"points = {total_points:5.2f} / {max_points:5.2f}")


def print_error_messages(errors: list) -> None:
    """pretty prints the returned error_messages

    Args:
        errors (list): list of string containing the error messages
    """

    if errors:
        top_out("error_messages", left=_C_LEFT, right=_C_RIGHT)
        for error in errors:
            for line in error.splitlines():
                print_long_line(line)
            out("")


def print_lines(file: dict, part: str) -> None:
    """pretty prints a part of a dictionary

    Args:
        file (dict): result of one test file as dictionary
        part (str): key of the dictionary, which values are to be pretty printed
    """
    if file.get(part, None):
        top_out(part, left=_C_LEFT, right=_C_RIGHT)
        for line in file[part].splitlines():
            print_long_line(line)


def print_long_line(long_line: str) -> None:
    """wraps a long string and pretty prints it

    Args:
        long_line (str): text to be wrapped, should not contain line breaks
    """
    if long_line.strip() == "":
        out("")
    else:
        for line in textwrap.wrap(long_line, 70):
            out(line.replace("\t", "  "))


def create_payload(directory_name: str) -> tuple[str, bytes]:
    """creates the payload for the given directory based on
    the .co file and the listed files

    Args:
        directory_name (str): directory containing .co file and sources

    Returns:
        tuple[str, bytes]: target_url, payload
    """
    # read control file with target url, validation token
    # and expected files
    co_file = read_utf8_file(directory_name, ".co").splitlines()

    # fill files_attributes
    files_attributes = {}
    for i in range(2, len(co_file)):
        file_name, file_id = co_file[i].split("=")
        out(" " + file_name)
        files_attributes[str(i - 2)] = {
            "file_id": int(file_id),
            "content": read_utf8_file(directory_name, file_name),
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


def post_payload_as_json(url: str, payload: bytes) -> Response:
    """posts the given payload to the given url as application/json

    Args:
        url (str): target_url to POST the payload
        payload (bytes): payload

    Returns:
        Response: Object containing content, headers ans status
    """
    request = urllib.request.Request(url, payload, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request) as http_response:
            response = Response(
                http_response.read(), http_response.getheaders(), http_response.status
            )
    except urllib.error.HTTPError as he:
        # raised if the response code from the POST request is not 2xx
        response = Response(he.fp.read(), he.headers.items(), he.code)

    return response


def read_utf8_file(directory_name: str, file_name: str) -> str:
    """reads a file as string assuming the file is utf-8 encoded

    Args:
        directory_name (str): name of the directory, where the file can be found
        file_name (str): name of the file

    Returns:
        str: content of the file
    """
    with open(os.path.join(directory_name, file_name), encoding="utf-8") as file:
        return file.read()


def check_response(response: Response) -> list:
    """checks whether the response can be processed further.
    Only proceed if status is 201 (created) and content is announced as json

    Args:
        response (Response): Response with content, headers and status

    Returns:
        list: result, a list containing dictionaries
    """
    assert response.status == http.HTTPStatus.CREATED, response
    is_json = get_header(response.headers, "content-type").startswith("application/json")
    assert is_json, response
    result = json.loads(response.content)
    assert isinstance(result, list), response
    if len(result) > 0:  # There are tests"
        assert isinstance(result[0], dict), response
        assert "filename" in result[0], response

    return result


def print_error_response(response: Response) -> None:
    """prints status, headers, code of an unprocessable response
    special treatment for status 422 and 503

    Args:
        response (Response): Response with content, headers and status
    """
    print("\n--- Unexpected response from server (CodeOcean) ---")

    print(f"Http-Status:{response.status} ({http.HTTPStatus(response.status).phrase})")
    if get_header(response.headers, "content-type").startswith("application/json"):
        body = json.loads(response.content)
        if isinstance(body, dict):
            print(body.get("message"), "")

    if response.status == http.HTTPStatus.SERVICE_UNAVAILABLE:
        print("\nMost likely no execution environment is currently available.")
        print("Try again later.")
        return

    if response.status == http.HTTPStatus.UNPROCESSABLE_ENTITY:
        print("\nThe server cannot process the payload. This is an error.")
        print("in the script. Please report.")
        return

    print("\n----- Http-Headers:")
    for header in response.headers:
        print(header[0], ":", header[1])

    print("\n----- Content (utf-8 decoded):")
    print(response.content.decode())


def get_header(headers, name: str) -> str:
    """gets a header from headers

    Args:
        headers (iterable): list of pairs
        name (str): name of a header field

    Returns:
        str: value of the header field or empty string if not found
    """
    for header in headers:
        if header[0].lower() == name.lower():
            return header[1]
    return ""


def out(middle="", left=_C_VERT, right=_C_VERT, fill=" "):
    _len = len(left) + len(middle) + len(right)
    print(left + middle, end="")
    if _len <= _COLS:
        print((_COLS - _len) * fill + right)


def bottom_out():
    out(_C_HOR, _C_BL, _C_BR, _C_HOR)


def top_out(text, dist=25, left=_C_UL, right=_C_UR):
    if len(text) > 0:
        out(dist * _C_HOR + " " + text + " ", left, right, _C_HOR)
    else:
        out("", left, right, _C_HOR)


def main() -> None:
    """static main method called if script is not imported"""
    parser = argparse.ArgumentParser(
        description=f"CodeOcean Remote Client v{_VERSION} (by wrglprmft)"
    )
    parser.add_argument("directory", help="directory with .co file", default=".", nargs="?")
    parser.add_argument("-o", "--stdout", action="store_true", help="output also stdout")
    parser.add_argument("-e", "--stderr", action="store_true", help="output also stderr")
    parser.add_argument("--version", action="store_true", help="show version and exit")
    parameter = parser.parse_args()

    if parameter.version:
        print(f"Version {_VERSION}")
        return

    evaluate(parameter.directory, parameter.stderr, parameter.stdout)


# don't run while being imported
if __name__ == "__main__":
    main()
