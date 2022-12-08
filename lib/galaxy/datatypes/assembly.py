"""
velvet datatypes
James E Johnson - University of Minnesota
for velvet assembler tool in galaxy
"""

import logging
import os
import re
from typing import TYPE_CHECKING

from galaxy.datatypes import (
    data,
    sequence,
)
from galaxy.datatypes.data import GeneratePrimaryFileDataset
from galaxy.datatypes.metadata import MetadataElement
from galaxy.datatypes.sniff import (
    build_sniff_from_prefix,
    FilePrefix,
)
from galaxy.datatypes.text import Html

if TYPE_CHECKING:
    from galaxy.model import DatasetInstance

log = logging.getLogger(__name__)


@build_sniff_from_prefix
class Amos(data.Text):
    """Class describing the AMOS assembly file"""

    edam_data = "data_0925"
    edam_format = "format_3582"
    file_ext = "afg"

    def sniff_prefix(self, file_prefix: FilePrefix) -> bool:
        """
        Determines whether the file is an amos assembly file format
        Example::

          {CTG
          iid:1
          eid:1
          seq:
          CCTCTCCTGTAGAGTTCAACCGA-GCCGGTAGAGTTTTATCA
          .
          qlt:
          DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD
          .
          {TLE
          src:1027
          off:0
          clr:618,0
          gap:
          250 612
          .
          }
          }
        """
        for line in file_prefix.line_iterator():
            if not line:
                break  # EOF
            line = line.strip()
            if line:  # first non-empty line
                if line.startswith("{"):
                    if re.match(r"{(RED|CTG|TLE)$", line):
                        return True
        return False


@build_sniff_from_prefix
class Sequences(sequence.Fasta):
    """Class describing the Sequences file generated by velveth"""

    edam_data = "data_0925"
    file_ext = "sequences"

    def sniff_prefix(self, file_prefix: FilePrefix) -> bool:
        """
        Determines whether the file is a velveth produced  fasta format
        The id line has 3 fields separated by tabs: sequence_name  sequence_index category::

          >SEQUENCE_0_length_35   1       1
          GGATATAGGGCCAACCCAACTCAACGGCCTGTCTT
          >SEQUENCE_1_length_35   2       1
          CGACGAATGACAGGTCACGAATTTGGCGGGGATTA
        """
        fh = file_prefix.string_io()
        for line in fh:
            line = line.strip()
            if line:  # first non-empty line
                if line.startswith(">"):
                    if not re.match(r">[^\t]+\t\d+\t\d+$", line):
                        return False
                    # The next line.strip() must not be '', nor startwith '>'
                    line = fh.readline().strip()
                    if line == "" or line.startswith(">"):
                        return False
                    return True
                else:
                    return False
        return False


@build_sniff_from_prefix
class Roadmaps(data.Text):
    """Class describing the Sequences file generated by velveth"""

    edam_format = "format_2561"
    file_ext = "roadmaps"

    def sniff_prefix(self, file_prefix: FilePrefix) -> bool:
        """
        Determines whether the file is a velveth produced RoadMap::
          142858  21      1
          ROADMAP 1
          ROADMAP 2
          ...
        """

        fh = file_prefix.string_io()
        for line in fh:
            line = line.strip()
            if line:  # first non-empty line
                if not re.match(r"\d+\t\d+\t\d+$", line):
                    return False
                # The next line.strip() should be 'ROADMAP 1'
                line = fh.readline().strip()
                return bool(re.match(r"ROADMAP \d+$", line))
            else:
                return False  # we found a non-empty line, but it's not a fasta header
        return False


class Velvet(Html):
    MetadataElement(
        name="base_name", desc="base name for velveth dataset", default="velvet", readonly=True, set_in_upload=True
    )
    MetadataElement(
        name="paired_end_reads", desc="has paired-end reads", default="False", readonly=False, set_in_upload=True
    )
    MetadataElement(name="long_reads", desc="has long reads", default="False", readonly=False, set_in_upload=True)
    MetadataElement(
        name="short2_reads", desc="has 2nd short reads", default="False", readonly=False, set_in_upload=True
    )
    composite_type = "auto_primary_file"
    file_ext = "velvet"

    def __init__(self, **kwd):
        super().__init__(**kwd)
        self.add_composite_file(
            "Sequences",
            mimetype="text/html",
            description="Sequences",
            substitute_name_with_metadata=None,
            is_binary=False,
        )
        self.add_composite_file(
            "Roadmaps",
            mimetype="text/html",
            description="Roadmaps",
            substitute_name_with_metadata=None,
            is_binary=False,
        )
        self.add_composite_file(
            "Log",
            mimetype="text/html",
            description="Log",
            optional="True",
            substitute_name_with_metadata=None,
            is_binary=False,
        )

    def generate_primary_file(self, dataset: GeneratePrimaryFileDataset) -> str:
        log.debug(f"Velvet log info  JJ generate_primary_file {dataset}")
        rval = ["<html><head><title>Velvet Galaxy Composite Dataset </title></head><p/>"]
        rval.append("<div>This composite dataset is composed of the following files:<p/><ul>")
        for composite_name, composite_file in self.get_composite_files(dataset=dataset).items():
            fn = composite_name
            log.debug(f"Velvet log info  JJ generate_primary_file {fn} {composite_file}")
            opt_text = ""
            if composite_file.optional:
                opt_text = " (optional)"
            if composite_file.get("description"):
                rval.append(
                    f"<li><a href=\"{fn}\" type=\"text/plain\">{fn} ({composite_file.get('description')})</a>{opt_text}</li>"
                )
            else:
                rval.append(f'<li><a href="{fn}" type="text/plain">{fn}</a>{opt_text}</li>')
        rval.append("</ul></div></html>")
        return "\n".join(rval)

    def regenerate_primary_file(self, dataset: "DatasetInstance") -> None:
        """
        cannot do this until we are setting metadata
        """
        log.debug(f"Velvet log info  {'JJ regenerate_primary_file'}")
        gen_msg = ""
        try:
            efp = dataset.extra_files_path
            log_path = os.path.join(efp, "Log")
            with open(log_path) as f:
                log_content = f.read(1000)
            log_msg = re.sub(r"/\S*/", "", log_content)
            log.debug(f"Velveth log info  {log_msg}")
            paired_end_reads = re.search(r"-(short|long)Paired", log_msg) is not None
            dataset.metadata.paired_end_reads = paired_end_reads
            long_reads = re.search(r"-long", log_msg) is not None
            dataset.metadata.long_reads = long_reads
            short2_reads = re.search(r"-short(Paired)?2", log_msg) is not None
            dataset.metadata.short2_reads = short2_reads
            dataset.info = re.sub(r".*velveth \S+", "hash_length", re.sub(r"\n", " ", log_msg))
            if paired_end_reads:
                gen_msg = f"{gen_msg} Paired-End Reads"
            if long_reads:
                gen_msg = f"{gen_msg} Long Reads"
            if len(gen_msg) > 0:
                gen_msg = f"Uses: {gen_msg}"
        except Exception:
            log.debug(f"Velveth could not read Log file in {efp}")
        log.debug(f"Velveth log info  {gen_msg}")
        rval = ["<html><head><title>Velvet Galaxy Composite Dataset </title></head><p/>"]
        # rval.append('<div>Generated:<p/><code> %s </code></div>' %(re.sub('\n','<br>',log_msg)))
        rval.append(f"<div>Generated:<p/> {gen_msg} </div>")
        rval.append("<div>Velveth dataset:<p/><ul>")
        for composite_name, composite_file in self.get_composite_files(dataset=dataset).items():
            fn = composite_name
            log.debug(f"Velvet log info  JJ regenerate_primary_file {fn} {composite_file}")
            if re.search("Log", fn) is None:
                opt_text = ""
                if composite_file.optional:
                    opt_text = " (optional)"
                if composite_file.get("description"):
                    rval.append(
                        f"<li><a href=\"{fn}\" type=\"text/plain\">{fn} ({composite_file.get('description')})</a>{opt_text}</li>"
                    )
                else:
                    rval.append(f'<li><a href="{fn}" type="text/plain">{fn}</a>{opt_text}</li>')
        rval.append("</ul></div></html>")
        with open(dataset.file_name, "w") as f:
            f.write("\n".join(rval))
            f.write("\n")

    def set_meta(self, dataset: "DatasetInstance", **kwd) -> None:
        Html.set_meta(self, dataset, **kwd)
        self.regenerate_primary_file(dataset)
