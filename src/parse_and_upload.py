#!/usr/bin/env python3

"""
Parse Objects file, Use that to create an html index. That html index should get uploaded to COAD.io
"""

import argparse
import logging
import os
import urllib.parse
import json
import time
import sys

import requests
import sphobjinv
import jinja2


def get_argparse():
    """
    Let's grab my runtime options
    """

    parser = argparse.ArgumentParser()

    parser.add_argument("-b", "--uribase", help="Hosted Sphinx Domain", required=False,
                        default=os.environ.get("SPHINX_BASE_URI"))
    parser.add_argument("-f", "--objectfile", help="Intersphinx File", required=False,
                        default=os.environ.get("OBJECTS_FILE", "build/html/objects.inv"))
    parser.add_argument("-i", "--docID", help="CodaIO Document (Category) ID", required=False,
                        default=os.environ.get("DOCID"))
    parser.add_argument("-p", "--pageID", help="PageID for Coda", required=False,
                        default=os.environ.get("PAGEID"))
    parser.add_argument("--token", help="Coda.io API Token", required=False,
                        default=os.environ.get("CODA_TOKEN"))
    parser.add_argument("-v", "--verbose", action="append_const", help="Verbosity Controls",
                        const=1, default=[])
    parser.add_argument("-t", "--template", help="HTML Template File", required=False,
                        default=os.environ.get("TEMPLATE", "src/template.html.jinja"))
    parser.add_argument("-C", "--confirm", help="Confirm Deletion", action="store_true", default=False)

    return parser


if __name__ == "__main__":

    parser = get_argparse()

    args = parser.parse_args()

    VERBOSE = len(args.verbose)

    if VERBOSE == 0:
        logging.basicConfig(level=logging.ERROR)
    elif VERBOSE == 1:
        logging.basicConfig(level=logging.WARNING)
    elif VERBOSE == 2:
        logging.basicConfig(level=logging.INFO)
    elif VERBOSE > 2:
        logging.basicConfig(level=logging.DEBUG)

    logger = logging.getLogger("parse_and_upload.py")

    if os.path.isfile(args.objectfile) is False:
        raise FileNotFoundError("No Inventory file found at {}.".format(args.objectfile))
    elif os.path.isfile(args.template) is False:
        raise FileNotFoundError("No Template file found at {}.".format(args.template))

    else:
        response_object = {"update_time": time.ctime()}
        intersphinx_inventory = sphobjinv.Inventory(args.objectfile)

        with open(args.template, "r") as template_fobj:
            template_string = template_fobj.read()

            html_template = jinja2.Environment(loader=jinja2.BaseLoader,
                                              autoescape=jinja2.select_autoescape(
                                                  enabled_extensions=('html', 'xml'),
                                                  default_for_string=False,
                                              )).from_string(template_string)

            rendered_html = html_template.render({"inventory": intersphinx_inventory,
                                                  "baseuri": args.uribase})

            #print(rendered_html)

        ## Coda Stuff

        pages_uri = urllib.parse.urlparse("https://coda.io/apis/v1/docs/{doc_id}/pages/{page_id}".format(doc_id=args.docID,
                                                                                                           page_id=args.pageID))

        #print(pages_uri.geturl())

        try:
            page_response = requests.get(pages_uri.geturl(),
                                         headers={"Authorization": "Bearer " + args.token})

            page_response.raise_for_status()
        except Exception as page_error:
            logger.error("Unable to find Specified Pages. Possibly a Permissions or Existence Error.")
            logger.debug(page_error)
            sys.exit(1)
        else:

            update_payload = {
                "name": intersphinx_inventory.project,
                "subtitle": "Generated Time: {ctime}".format(ctime=response_object["update_time"]),
                "contentUpdate": {
                    "insertionMode": "replace",
                    "canvasContent": {
                        "format": "html",
                        "content": rendered_html
                    }
                }
            }


            try:
                pu_response = requests.put(pages_uri.geturl(),
                                             headers={"Authorization": "Bearer " + args.token,
                                                      "Content-Type": "application/json"
                                                      },
                                             json=update_payload
                                             )
                pu_response.raise_for_status()
            except Exception as pu_error:
                logger.error("Unable to Update the Page.")
                logger.debug(pu_error)
                sys.exit(1)
            else:
                # I've updated the page
                response_object = {**response_object, **pu_response.json()}

    print(json.dumps(response_object, indent=4))
    sys.exit(0)
