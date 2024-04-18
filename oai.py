import sys
import lxml.etree as ET

from elasticsearch import Elasticsearch
from datetime import datetime,timezone
class OAIProvider:
    def __init__(self, hosts):
        # Initialize the OAI provider
        self.es = hosts
        self.publication_json = {}
        self.document_xml = ET.Element("dublin_core")

    def get_oai_data(self, pub_id):
        if self.es.exists(index="publications", id=pub_id):
            publication = self.es.get(index="publications", id=pub_id)
            self.publication_json = publication["_source"]
            return self.generate_xml_document(pub_id)
        else:
            print(f"Error loading publication: {pub_id}")

    def generate_xml_document(self, pub_id):
        # Setup namespace for xsi
        ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
        # Setup namespace for xlink
        ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

        root = ET.Element("OAI-PMH")
        #root.set("xsi:schemaLocation", "http://www.openarchives.org/OAI/2.0/ http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd")
        # set xsi:schemaLocation="http://www.openarchives.org/OAI/2.0/ http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd"
        root.set("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation", "http://www.openarchives.org/OAI/2.0/ http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd")
#        ET.SubElement(root, "responseDate").text = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
#        ET.SubElement(root, "request", metadataPrefix="mods", identifier="oai:gup.ub.gu.se/329099", verb="GetRecord").text = "https://gup.ub.gu.se/oai"
        get_record = ET.SubElement(root, "GetRecord")
        record = ET.SubElement(get_record, "record")
        header = ET.SubElement(record, "header")

        self.get_header(header, pub_id)
        metadata = ET.SubElement(record, "metadata")
        return self.get_metadata(metadata)

    def get_header(self, header, pub_id):
        # Set the identifier element in the header
        ET.SubElement(header, "identifier").text = f"oai:gup.ub.gu.se/{pub_id}"

        # Get the timestamp from the publication JSON
        timestamp = self.publication_json["updated_at"]

        # Set the datestamp element in the header
        ET.SubElement(header, "datestamp").text = timestamp  # TODO: format timestamp

    def get_metadata(self, metadata):
        mods = self.set_mods(metadata)
        ET.SubElement(mods, "recordInfo").text = "gu"
        self.get_identifiers(mods)
        self.get_title(mods)
        self.get_categories(mods)
        self.get_abstract(mods)
        self.get_subjects(mods)
        self.get_language(mods)
        self.get_genre(mods)
        self.get_authors(mods)
        self.get_notes(mods)
        self.get_origin_info(mods)
        self.get_type_of_resource(mods)
        return mods

    def is_monograph(self):
        publication_type_id = self.publication_json["publication_type_id"]
        # Publication is a monograph if the publication type is one of the following
        # publication_book
        # publication_edited-book
        # publication_report
        # publication_doctoral-thesis
        # publication_licenciate-thesis
        return publication_type_id in [8, 9, 16, 17, 19]

    def get_abstract(self, mods):
        abstract = self.publication_json["abstract"]
        if abstract and abstract is not None:
            ET.SubElement(mods, "abstract").text = abstract

    def get_categories(self, mods):
        categories = self.publication_json["categories"]
        [self.add_category_as_classification(mods, category) for category in categories]
        # Get the categories as subjects for each language in ["eng", "swe"]
        [self.add_category_as_subject(mods, category, lang) for category in categories for lang in ["eng", "swe"]]

    def add_category_as_classification(self, mods, category):
        classification = ET.SubElement(mods, "classification")
        classification.set("authority", "ssif")
        topic = ET.SubElement(classification, "topic")
        topic.text = str(category["svep_id"])

    def get_category_field_name(self, lang):
        return "name_sv" if lang == "swe" else "name_en"

    def add_category_as_subject(self, mods, category, lang):
        subject = ET.SubElement(mods, "subject")
        subject.set("lang", lang)
        subject.set("authority", "uka.se")
        subject.set("{http://www.w3.org/1999/xlink}href", str(category["svep_id"]))  # Fix: Replace 'xlink:href' with 'href'
        topic = ET.SubElement(subject, "topic")
        topic.text = category[self.get_category_field_name(lang)]  # Fix: Add 'self.' before 'get_category_field_name'

    def get_identifiers(self, mods):
        identifiers = self.publication_json["publication_identifiers"]
        self.add_uri(mods, self.publication_json["publication_id"])
        if self.is_monograph():
            self.add_isbn(mods, self.publication_json["isbn"])
        [self.add_identifier(mods, identifier) for identifier in identifiers]

    def add_uri(self, mods, publication_id):
        uri = ET.SubElement(mods, "identifier")
        uri.set("type", "uri")
        uri.text = "https://gup-lab.ub.gu.se/publication/" + str(publication_id)

    def add_isbn(self, mods, isbn):
        if isbn and isbn is not None:
            identifier = ET.SubElement(mods, "identifier")
            identifier.set("type", "isbn")
            identifier.text = isbn

    def add_identifier(self, mods, identifier_source):
        identifier = ET.SubElement(mods, "identifier")
        identifier.set("type", self.get_identifier_code(identifier_source["identifier_code"]))
        identifier.text = identifier_source["identifier_value"]

    def get_identifier_code(self, identifier):
        identifier_mapping = {
            "isi-id": "isi",
            "pubmed": "pmid",
            "handle": "hdl",
            "doi": "doi",
            "scopus-id": "scopus",
            "libris-id": "se-libr"
        }
        return identifier_mapping.get(identifier, identifier)

    def get_title(self, mods):
        titleInfo = ET.SubElement(mods, "titleInfo")
        ET.SubElement(titleInfo, "title").text = self.publication_json["title"]

    def get_authors(self, mods):
        authors = self.publication_json["authors"]
        [self.add_author(mods, author) for author in authors]

    def add_author(self, mods, author):
        person = author['person'][0]
        print(person)
        xkonto = self.get_person_identifier_value(person["identifiers"], "xkonto")
        name = ET.SubElement(mods, "name")
        name.set("type", "personal")
        if xkonto:
            name.set("authority", "gu")
        fname = ET.SubElement(name, "namePart")
        fname.set("type", "given")
        fname.text = person["first_name"]
        lname = ET.SubElement(name, "namePart")
        lname.set("type", "family")
        lname.text = person["last_name"]

        if "year_of_birth" in person and person["year_of_birth"] is not None:
            bdate = ET.SubElement(name, "namePart")
            bdate.set("type", "date")
            bdate.text = str(person["year_of_birth"])

        # Get the role code based on the publication type
        role_code = self.get_role_code(self.publication_json["publication_type_id"])
        role = ET.SubElement(name, "role")
        roleTerm = ET.SubElement(role, "roleTerm")
        roleTerm.set("type", "code")
        roleTerm.text = role_code

        if xkonto:
            nameIdentifier = ET.SubElement(name, "nameIdentifier")
            nameIdentifier.set("type", "gu")
            nameIdentifier.text = xkonto
        orcid = self.get_person_identifier_value(person["identifiers"], "orcid")
        if orcid:
            nameIdentifier = ET.SubElement(name, "nameIdentifier")
            nameIdentifier.set("type", "orcid")
            nameIdentifier.text = orcid
        # affiliations = author["affiliations"]
        # [self.add_affiliation(name, affiliation) for affiliation in affiliations]

    def add_affiliation(self, name, affiliation_source):
        affiliation = ET.SubElement(name, "affiliation")
        affiliation.text = affiliation_source["name_sv"]

    def get_person_identifier_value(self, identifiers, identifier_code):
        for identifier in identifiers:
            if identifier["type"] == identifier_code:
                return identifier["value"]
        return None

    def get_genre(self, mods):
        publication_type_id = self.publication_json["publication_type_id"]
        publication_type_info = self.get_publication_type_info(publication_type_id)

        # return content_type genre and output_type genre that will generete xml in this form:
        #<genre authority="kb.se" type="outputType">publication/doctoral-thesis</genre>
        #<genre authority="svep" type="contentType">vet</genre>
        output_type = ET.SubElement(mods, "genre")
        output_type.set("authority", "kb.se")
        output_type.set("type", "outputType")
        output_type.text = publication_type_info["output_type"]
        content_type = ET.SubElement(mods, "genre")
        content_type.set("authority", "svep")
        content_type.set("type", "contentType")
        content_type.text = publication_type_info["content_type"]

    # Get the role code based on the specified mapping rules. If not found return defaule value "aut"
    def get_role_code(self, publication_type_id):
        # Get the roles based on the publication type and the role mapping
        # TODO: Use publication type code when available in elasticsearch index
        role_mapping = {
            8: "edt", #publication_edited-book
            28: "edt", #publication_textcritical-edition
            44: "edt", #publication_journal-issue
            45: "edt" #conference_proceeding
        }
        return role_mapping.get(publication_type_id, "aut")


    def get_publication_type_info(self, publication_type_id):
        # Get the content_type and output_type based on the publication type based on the folling mappings

        # mapping publication_type_code to a list of unused value, content_type and output_type
        #    'conference_other' => ['kon', 'vet', 'conference/other'],
        #    'conference_paper' => ['kon', 'ref', 'conference/paper'],
        #    'conference_poster' => ['kon', 'vet', 'conference/poster'],
        #    'publication_journal-article' => ['art', 'ref', 'publication/journal-article'],
        #    'publication_magazine-article' => ['art', 'vet', 'publication/magazine-article'],
        #    'publication_edited-book' => ['sam', 'vet', 'publication/edited-book'],
        #    'publication_book' => ['bok', 'vet', 'publication/book'],
        #    'publication_book-chapter' => ['kap', 'vet', 'publication/book-chapter'],
        #    'intellectual-property_patent' => ['pat', 'vet', 'intellectual-property/patent'],
        #    'publication_report' => ['rap', 'vet', 'publication/report'],
        #    'publication_doctoral-thesis' => ['dok', 'vet', 'publication/doctoral-thesis'],
        #    'publication_book-review' => ['rec', 'vet', 'publication/book-review'],
        #    'publication_licentiate-thesis' => ['lic', 'vet', 'publication/licentiate-thesis'],
        #    'other' => ['ovr', 'vet', 'publication/other'],
        #    'publication_review-article' => ['for', 'ref', 'publication/review-article'],
        #    'artistic-work_scientific_and_development' => ['kfu', 'vet', 'artistic-work'], # ?????
        #    'publication_textcritical-edition' => ['ovr', 'vet', 'publication/critical-edition'],
        #    'publication_textbook' => ['bok', 'vet', 'publication/book'],
        #    'artistic-work_original-creative-work' => ['kfu', 'vet', 'artistic-work/original-creative-work'],
        #    'publication_editorial-letter' => ['art', 'vet', 'publication/editorial-letter'],
        #    'publication_report-chapter' => ['kap', 'vet', 'publication/report-chapter'],
        #    'publication_newspaper-article' => ['art', 'pop', 'publication/newspaper-article'],
        #    'publication_encyclopedia-entry' => ['kap', 'vet', 'publication/encyclopedia-entry'],
        #    'publication_journal-issue' => ['ovr', 'vet', 'publication/journal-issue'],
        #    'conference_proceeding' => ['pro', 'vet', 'conference/proceeding'],
        #    'publication_working-paper' => ['ovr', 'vet', 'publication/working-paper']}

        # mapping publication_type_id to publication_type_code
        #   1 | conference_other
        #   2 | conference_paper
        #   3 | conference_poster
        #   5 | publication_journal-article
        #   7 | publication_magazine-article
        #   8 | publication_edited-book
        #   9 | publication_book
        #  10 | publication_book-chapter
        #  13 | intellectual-property_patent
        #  16 | publication_report
        #  17 | publication_doctoral-thesis
        #  18 | publication_book-review
        #  19 | publication_licentiate-thesis
        #  21 | other
        #  22 | publication_review-article
        #  23 | artistic-work_scientific_and_development
        #  28 | publication_textcritical-edition
        #  30 | publication_textbook
        #  34 | artistic-work_original-creative-work
        #  40 | publication_editorial-letter
        #  41 | publication_report-chapter
        #  42 | publication_newspaper-article
        #  43 | publication_encyclopedia-entry
        #  44 | publication_journal-issue
        #  45 | conference_proceeding
        #  46 | publication_working-paper

        # TODO: Use publication type code when available in elasticsearch index
        publication_type_mapping = {
            1: {'content_type': 'kon', 'output_type': 'conference/other'}, # conference_other
            2: {'content_type': 'kon', 'output_type': 'conference/paper'}, # conference_paper
            3: {'content_type': 'kon', 'output_type': 'conference/poster'}, # conference_poster
            5: {'content_type': 'art', 'output_type': 'publication/journal-article'}, # publication_journal-article
            7: {'content_type': 'art', 'output_type': 'publication/magazine-article'}, # publication_magazine-article
            8: {'content_type': 'sam', 'output_type': 'publication/edited-book'}, # publication_edited-book
            9: {'content_type': 'bok', 'output_type': 'publication/book'}, # publication_book
            10: {'content_type': 'kap', 'output_type': 'publication/book-chapter'}, # publication_book-chapter
            13: {'content_type': 'pat', 'output_type': 'intellectual-property/patent'}, # intellectual-property_patent
            16: {'content_type': 'rap', 'output_type': 'publication/report'}, # publication_report
            17: {'content_type': 'dok', 'output_type': 'publication/doctoral-thesis'}, # publication_doctoral-thesis
            18: {'content_type': 'rec', 'output_type': 'publication/book-review'}, # publication_book-review
            19: {'content_type': 'lic', 'output_type': 'publication/licentiate-thesis'}, # publication_licentiate-thesis
            21: {'content_type': 'ovr', 'output_type': 'publication/other'}, # other
            22: {'content_type': 'for', 'output_type': 'publication/review-article'}, # publication_review-article
            23: {'content_type': 'kfu', 'output_type': 'artistic-work'}, # artistic-work_scientific_and_development
            28: {'content_type': 'ovr', 'output_type': 'publication/critical-edition'}, # publication_textcritical-edition
            30: {'content_type': 'bok', 'output_type': 'publication/book'}, # publication_textbook
            34: {'content_type': 'kfu', 'output_type': 'artistic-work/original-creative-work'}, # artistic-work_original-creative-work
            40: {'content_type': 'art', 'output_type': 'publication/editorial-letter'}, # publication_editorial-letter
            41: {'content_type': 'kap', 'output_type': 'publication/report-chapter'}, # publication_report-chapter
            42: {'content_type': 'art', 'output_type': 'publication/newspaper-article'}, # publication_newspaper-article
            43: {'content_type': 'kap', 'output_type': 'publication/encyclopedia-entry'}, # publication_encyclopedia-entry
            44: {'content_type': 'ovr', 'output_type': 'publication/journal-issue'}, # publication_journal-issue
            45: {'content_type': 'pro', 'output_type': 'conference/proceeding'}, # conference_proceeding
            46: {'content_type': 'ovr', 'output_type': 'publication/working-paper'} # publication_working-paper
        }
        return publication_type_mapping.get(publication_type_id, {'content_type': 'ovr', 'output_type': 'publication/other'})


    def get_language(self, mods):
        if "language" in self.publication_json:
            language_code = self.get_language_code(self.publication_json["language"])
            # return language in this form:
            #<language>
            #<languageTerm type="code" authority="iso639-2b">language_code</languageTerm>
            #</language>
            language = ET.SubElement(mods, "language")
            languageTerm = ET.SubElement(language, "languageTerm")
            languageTerm.set("type", "code")
            languageTerm.set("authority", "iso639-2b")
            languageTerm.text = language_code


    # Get the language code based on the specified mapping rules. If not found return "und"
    def get_language_code(self, language):
        language_mapping = {
            "en": "eng",
            "eng": "eng",
            "sv": "swe",
            "swe": "swe",
            "ar": "ara",
            "ara": "ara",
            "bs": "bos",
            "bos": "bos",
            "bg": "bul",
            "bul": "bul",
            "zh": "chi",
            "chi": "chi",
            "hr": "hrv",
            "hrv": "hrv",
            "cs": "cze",
            "cze": "cze",
            "da": "dan",
            "dan": "dan",
            "nl": "dut",
            "dut": "dut",
            "fi": "fin",
            "fin": "fin",
            "fr": "fre",
            "fre": "fre",
            "de": "ger",
            "ger": "ger",
            "el": "gre",
            "gre": "gre",
            "he": "heb",
            "heb": "heb",
            "hu": "hun",
            "hun": "hun",
            "is": "ice",
            "ice": "ice",
            "it": "ita",
            "ita": "ita",
            "ja": "jpn",
            "jpn": "jpn",
            "ko": "kor",
            "kor": "kor",
            "la": "lat",
            "lat": "lat",
            "lv": "lav",
            "lav": "lav",
            "no": "nor",
            "nor": "nor",
            "pl": "pol",
            "pol": "pol",
            "pt": "por",
            "por": "por",
            "ro": "rum",
            "rum": "rum",
            "ru": "rus",
            "rus": "rus",
            "sr": "srp",
            "srp": "srp",
            "sk": "slo",
            "slo": "slo",
            "sl": "slv",
            "slv": "slv",
            "es": "spa",
            "spa": "spa",
            "tr": "tur",
            "tur": "tur",
            "uk": "ukr",
            "ukr": "ukr"
        }
        return language_mapping.get(language, "und")

    def add_name(self, mods, name):
        pass
        # print(name)

    def get_subjects(self, mods):
        subjects = self.publication_json["keywords"]
        print(self.publication_json)
        # Split the string and add each subject to the xml, if None return empty list
        # trim each subject
        []
        if subjects and subjects is not None:
           [self.add_subject(mods, subject.strip()) for subject in subjects.split(",")]

    def add_subject(self, mods, subject):
        subject_element = ET.SubElement(mods, "subject")
        topic = ET.SubElement(subject_element, "topic")
        topic.text = subject

    def get_notes(self, mods):
        published_status = ET.SubElement(mods, "note")
        published_status.set("type", "publicationStatus")
        epub_ahead_of_print = self.publication_json["epub_ahead_of_print"]
        #if epub_ahead_of_print exists and is not empty then set text to "Epub ahead of print", otherwise set text to "Published"
        if epub_ahead_of_print and epub_ahead_of_print is not None:
            published_status.text = "Epub ahead of print"
        else:
            published_status.text = "Published"

        creator_count = ET.SubElement(mods, "note")
        creator_count.set("type", "creatorCount")
        creator_count.text = str(len(self.publication_json["authors"]))

    def get_origin_info(self, mods):
        # check that each element exists and is not None before adding it to the xml
        origin_info = ET.SubElement(mods, "originInfo")
        pubyear = self.publication_json["pubyear"]
        if pubyear and pubyear is not None:
            date_issued = ET.SubElement(origin_info, "dateIssued")
            date_issued.text = str(pubyear)
        publisher = self.publication_json["publisher"]
        if publisher and publisher is not None:
            publisher_element = ET.SubElement(origin_info, "publisher")
            publisher_element.text = publisher
        place = self.publication_json["place"]
        if place and place is not None:
            place_element = ET.SubElement(origin_info, "place")
            place_term = ET.SubElement(place_element, "placeTerm")
            place_term.text = place

    def get_type_of_resource(self, mods):
        publication_type_id = self.publication_json["publication_type_id"]
        type_of_resource = ET.SubElement(mods, "typeOfResource")
        type_of_resource.text = self.get_type_of_resource_code(publication_type_id)

    def get_type_of_resource_code(self, publication_type_id):
        type_of_resource_mapping = {
            23: "mixed material", # artistic-work_scientific_and_development
            34: "mixed material" # artistic-work_original-creative-work
        }
        return type_of_resource_mapping.get(publication_type_id, "text")

    def set_mods(self, metadata):
        mods = ET.SubElement(metadata, "mods")
        # mods.set("version", "3.7")
        # mods.set("xsi:schemaLocation", "http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-7.xsd")
        return mods

if __name__ == "__main__":   
    if len(sys.argv) < 2:
        print("Please provide a publication id")
        sys.exit()
    else:
        a = OAIProvider()
        pub_id = sys.argv[1]
        print(a.get_oai_data(pub_id))
