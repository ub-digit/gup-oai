from oai_repo import RecordHeader

import os
import sys
import lxml.etree as ET

from datetime import datetime
class OAIProvider:
    def __init__(self):
        # Initialize the OAI provider
        self.publication_json = {}

    def get_oai_data(self, publication):
        self.publication_json = publication["_source"]
        return self.generate_xml_document()

    def generate_xml_document(self):
        return self.get_metadata()

    def build_recordheader(self, publication):
        # Build a recordheader object
        header = RecordHeader()
        header.identifier = os.environ.get("IDENTIFIER_PREFIX") + "/" + str(publication['publication_id'])
        header.datestamp = self.format_timestamp(publication['updated_at'])
        header.setspecs = self.get_set_specs(publication)
        # set status to "deleted" if the publication is marked as deleted in the index
        header.status = "deleted" if self.get_deleted_status(publication) else None
        return header

    def format_timestamp(self, timestamp):
        # Convert the timestamp to the required format, it must handle both "%Y-%m-%dT%H:%M:%S.%f" and "%Y-%m-%dT%H:%M:%S" formats
        if '.' not in timestamp:
            timestamp = timestamp + ".0"
        return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f").strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_set_specs(self, publication):
        set_specs = []
        # Add GU to the set_specs if the affiliated attribute is true
        if publication.get("affiliated") and publication['affiliated'] == True:
            set_specs.append("gu")
        # TBD: Add other set_specs based on the categories, departments, etc.
        return set_specs

    def get_deleted_status(self, publication):
        # Check if the publication is marked as deleted in the index
        return publication['deleted'] == True

    def get_metadata(self):
        mods = self.set_mods()
        self.get_record_info(mods)
        self.get_identifiers(mods)
        self.get_title(mods)
        self.get_abstract(mods)
        self.get_categories(mods)
        self.get_subjects(mods)
        self.get_language(mods)
        self.get_genre(mods)
        self.get_authors(mods)
        self.get_notes(mods)
        self.get_origin_info(mods)
        self.get_related_item(mods)
        self.get_series(mods)
        self.get_location(mods)
        self.get_physical_description(mods)
        self.get_type_of_resource(mods)
        return mods

    def set_mods(self):

        NSMAP = {
            None: "http://www.loc.gov/mods/v3",
            "xlink": "http://www.w3.org/1999/xlink",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance"
        }

        mods = ET.Element("mods", nsmap=NSMAP)
        mods.set("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation", "http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-7.xsd")
        mods.set("version", "3.7")

        return mods

    def get_record_info(self, mods):
        # Set the recordInfo element in the mods
        record_info = ET.SubElement(mods, "recordInfo")
        record_info_element = ET.SubElement(record_info, "recordContentSource")
        record_info_element.text = "gu"


    def is_monograph(self):
        publication_type_code = self.publication_json["publication_type_code"]
        # Publication is a monograph if the publication type is one of the following
        # publication_book
        # publication_edited-book
        # publication_report
        # publication_doctoral-thesis
        # publication_licenciate-thesis
        return publication_type_code in ['publication_book', 'publication_edited-book', 'publication_report', 'publication_doctoral-thesis', 'publication_licentiate-thesis']

    def get_abstract(self, mods):
        abstract = self.publication_json["abstract"]
        if abstract and abstract is not None:
            ET.SubElement(mods, "abstract").text = self.sanitize(abstract)

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
        uri.text = os.environ.get("URI_PREFIX") + "/" + str(publication_id)

    def add_isbn(self, mods, isbn):
        if isbn and isbn is not None:
            identifier = ET.SubElement(mods, "identifier")
            identifier.set("type", "isbn")
            identifier.text = isbn

    def add_identifier(self, mods, identifier_source):
        identifier_code = self.get_identifier_code(identifier_source["identifier_code"])
        if identifier_code is not None:
            identifier = ET.SubElement(mods, "identifier")
            identifier.set("type", identifier_code)
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
        ET.SubElement(titleInfo, "title").text = self.sanitize(self.publication_json["title"])
        # Add the subtitle if it exists
        subtitle = self.publication_json["alt_title"]
        if subtitle and subtitle is not None:
            ET.SubElement(titleInfo, "subTitle").text = self.sanitize(subtitle)


    def get_authors(self, mods):
        authors = self.publication_json["authors"]
        if authors is not None:
            authors.sort(key=lambda x: x["position"][0]["position"])
            [self.add_author(mods, author) for author in authors]
        else:
            []

    def add_author(self, mods, author):
        #print(author)
        person = author['person'][0]
        xkonto = self.get_person_identifier_value(person["identifiers"], "xkonto")
        name = ET.SubElement(mods, "name")
        name.set("type", "personal")
        if xkonto:
            name.set("authority", "gu")
        fname = ET.SubElement(name, "namePart")
        fname.set("type", "given")
        fname.text = self.sanitize(person["first_name"])
        lname = ET.SubElement(name, "namePart")
        lname.set("type", "family")
        lname.text = self.sanitize(person["last_name"])

        if "year_of_birth" in person and person["year_of_birth"] is not None:
            bdate = ET.SubElement(name, "namePart")
            bdate.set("type", "date")
            bdate.text = str(person["year_of_birth"])

        # Get the role code based on the publication type
        role_code = self.get_role_code(self.publication_json["publication_type_code"])
        role = ET.SubElement(name, "role")
        roleTerm = ET.SubElement(role, "roleTerm")
        roleTerm.set("type", "code")
        roleTerm.set("authority", "marcrelator")
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

        # Add the affiliation if it exists
        self.add_affiliation(author['affiliations'], name)

    def add_affiliation(self, affiliations, mods):
        if affiliations is not None and self.is_author_affiliated(affiliations):
        # create affiliations as following:

        # each entry in the affiliation list will be added as an affiliation element as in following example:

        # "affiliations": [
        #   {
        #     "department_id": 1304,
        #     "name_en": "School of Public Administration",
        #     "name_sv": "Förvaltningshögskolan"
        #   },
        #   {
        #     "department_id": 1323,
        #     "name_en": "Centre for European Research (CERGU)",
        #     "name_sv": "Centrum för Europaforskning (CERGU)"
        #   }
        # ]

        #<affiliation lang="swe" authority="kb.se" xsi:type="mods:stringPlusLanguagePlusAuthority" valueURI="gu.se">Göteborgs universitet</affiliation>
        #<affiliation lang="swe" authority="gu.se" xsi:type="mods:stringPlusLanguagePlusAuthority" valueURI="gu.se/1304">Förvaltningshögskolan</affiliation>
        #<affiliation lang="swe" authority="gu.se" xsi:type="mods:stringPlusLanguagePlusAuthority" valueURI="gu.se/1323">Centrum för Europaforskning (CERGU)</affiliation>

        #<affiliation lang="eng" authority="kb.se" xsi:type="mods:stringPlusLanguagePlusAuthority" valueURI="gu.se">Gothenburg University</affiliation>
        #<affiliation lang="eng" authority="gu.se" xsi:type="mods:stringPlusLanguagePlusAuthority" valueURI="gu.se/1304">School of Public Administration</affiliation>
        #<affiliation lang="eng" authority="gu.se" xsi:type="mods:stringPlusLanguagePlusAuthority" valueURI="gu.se/1323">Centre for European Research (CERGU)</affiliation>

            affiliation_element = ET.SubElement(mods, "affiliation")
            affiliation_element.set("lang", "swe")
            affiliation_element.set("authority", "kb.se")
            affiliation_element.set("{http://www.w3.org/2001/XMLSchema-instance}type", "mods:stringPlusLanguagePlusAuthority")
            affiliation_element.set("valueURI", "gu.se")
            affiliation_element.text = "Göteborgs universitet"

            affiliation_element = ET.SubElement(mods, "affiliation")
            affiliation_element.set("lang", "eng")
            affiliation_element.set("authority", "kb.se")
            affiliation_element.set("{http://www.w3.org/2001/XMLSchema-instance}type", "mods:stringPlusLanguagePlusAuthority")
            affiliation_element.set("valueURI", "gu.se")
            affiliation_element.text = "Gothenburg University"

            for affiliation in affiliations:
                affiliation_element = ET.SubElement(mods, "affiliation")
                affiliation_element.set("lang", "swe")
                affiliation_element.set("authority", "gu.se")
                affiliation_element.set("{http://www.w3.org/2001/XMLSchema-instance}type", "mods:stringPlusLanguagePlusAuthority")
                affiliation_element.set("valueURI", f"gu.se/{affiliation['department_id']}")
                affiliation_element.text = self.sanitize(affiliation["name_sv"])

                affiliation_element = ET.SubElement(mods, "affiliation")
                affiliation_element.set("lang", "eng")
                affiliation_element.set("authority", "gu.se")
                affiliation_element.set("{http://www.w3.org/2001/XMLSchema-instance}type", "mods:stringPlusLanguagePlusAuthority")
                affiliation_element.set("valueURI", f"gu.se/{affiliation['department_id']}")
                affiliation_element.text = self.sanitize(affiliation["name_en"])



    def is_author_affiliated(self, affiliations):
        # an author is affiliated if there is at least one affiliation with a department_id other than 666 and 667
        return any(aff["department_id"] not in [666, 667] for aff in affiliations)

#    def is_any_author_affiliated(self, authors):
#        # check if any of the authors are affiliated, if authors is None return False
#        return any(self.is_author_affiliated(author["affiliations"]) for author in authors) if authors is not None else False

    def get_person_identifier_value(self, identifiers, identifier_code):
        for identifier in identifiers:
            if identifier["type"] == identifier_code:
                return identifier["value"]
        return None

    def get_genre(self, mods):
        publication_type_code = self.publication_json["publication_type_code"]
        ref_value = self.publication_json["ref_value"]
        publication_type_info = self.get_publication_type_info(publication_type_code, ref_value)

        # return content_type genre and output_type genre that will generete xml in this form:
        #<genre authority="kb.se" type="outputType">publication/doctoral-thesis</genre>
        #<genre authority="svep" type="contentType">vet</genre>
        output_type = ET.SubElement(mods, "genre")
        output_type.set("authority", "kb.se")
        output_type.set("type", "outputType")
        output_type.text = publication_type_info["output_type"]

        # Special handling for publication on artistic basis, set an extra outputType genre if artistic_basis is not None and is True
        if self.publication_json["artistic_basis"]:
            artistic_basis = ET.SubElement(mods, "genre")
            artistic_basis.set("authority", "kb.se")
            artistic_basis.set("type", "outputType")
            artistic_basis.text = "artistic-work"

        content_type = ET.SubElement(mods, "genre")
        content_type.set("authority", "svep")
        content_type.set("type", "contentType")
        content_type.text = publication_type_info["content_type"]

    # Get the role code based on the specified mapping rules. If not found return defaule value "aut"
    def get_role_code(self, publication_type_code):
        # Get the roles based on the publication type and the role mapping
        role_mapping = {
            'publication_edited-book': 'edt',
            'publication_textcritical-edition': 'edt',
            'publication_journal-issue': 'edt',
            'conference_proceeding': 'edt'
        }

        return role_mapping.get(publication_type_code, "aut")


    def get_publication_type_info(self, publication_type_code, ref_value = None):
        # Get the content_type and output_type based on the publication type
        publication_type_mapping = {
            'conference_other': {'content_type': 'vet', 'output_type': 'conference/other'},
            'conference_paper': {'content_type': 'ref', 'output_type': 'conference/paper'},
            'conference_poster': {'content_type': 'vet', 'output_type': 'conference/poster'},
            'publication_journal-article': {'content_type': 'ref', 'output_type': 'publication/journal-article'},
            'publication_magazine-article': {'content_type': 'vet', 'output_type': 'publication/magazine-article'},
            'publication_edited-book': {'content_type': 'vet', 'output_type': 'publication/edited-book'},
            'publication_book': {'content_type': 'vet', 'output_type': 'publication/book'},
            # Special handling for book chapters, set the content_type to "ref" if ref_value is not None and is 'ISREF', otherwise set it to "vet"
            'publication_book-chapter': {'content_type': 'ref' if ref_value == 'ISREF' else 'vet', 'output_type': 'publication/book-chapter'},
            'intellectual-property_patent': {'content_type': 'vet', 'output_type': 'intellectual-property/patent'},
            'publication_report': {'content_type': 'vet', 'output_type': 'publication/report'},
            'publication_doctoral-thesis': {'content_type': 'vet', 'output_type': 'publication/doctoral-thesis'},
            'publication_book-review': {'content_type': 'vet', 'output_type': 'publication/book-review'},
            'publication_licentiate-thesis': {'content_type': 'vet', 'output_type': 'publication/licentiate-thesis'},
            'other': {'content_type': 'vet', 'output_type': 'publication/other'},
            'publication_review-article': {'content_type': 'ref', 'output_type': 'publication/review-article'},
            'artistic-work_scientific_and_development': {'content_type': 'vet', 'output_type': 'artistic-work'},
            'publication_textcritical-edition': {'content_type': 'vet', 'output_type': 'publication/critical-edition'},
            'publication_textbook': {'content_type': 'vet', 'output_type': 'publication/book'},
            'artistic-work_original-creative-work': {'content_type': 'vet', 'output_type': 'artistic-work/original-creative-work'},
            'publication_editorial-letter': {'content_type': 'vet', 'output_type': 'publication/editorial-letter'},
            'publication_report-chapter': {'content_type': 'vet', 'output_type': 'publication/report-chapter'},
            'publication_newspaper-article': {'content_type': 'pop', 'output_type': 'publication/newspaper-article'},
            'publication_encyclopedia-entry': {'content_type': 'vet', 'output_type': 'publication/encyclopedia-entry'},
            'publication_journal-issue': {'content_type': 'vet', 'output_type': 'publication/journal-issue'},
            'conference_proceeding': {'content_type': 'vet', 'output_type': 'conference/proceeding'},
            'publication_working-paper': {'content_type': 'vet', 'output_type': 'publication/working-paper'}
        }
        return publication_type_mapping.get(publication_type_code, {'content_type': 'vet', 'output_type': 'publication/other'})


    def get_language(self, mods):
        if "publanguage" in self.publication_json:
            language_code = self.get_language_code(self.publication_json["publanguage"])
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

    def get_subjects(self, mods):
        subjects = self.publication_json["keywords"]
        # Split the string and add each subject to the xml, if None return empty list
        # trim each subject
        []
        if subjects and subjects is not None:
           subjects = self.sanitize(subjects)
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
        # set the text to the number of authors, set to 0 if authors is None
        creator_count.text = str(len(self.publication_json.get("authors", [])) if self.publication_json.get("authors") is not None else 0)

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
            publisher_element.text = self.sanitize(publisher)
        place = self.publication_json["place"]
        if place and place is not None:
            place_element = ET.SubElement(origin_info, "place")
            place_term = ET.SubElement(place_element, "placeTerm")
            place_term.text = self.sanitize(place)

    def get_related_item(self, mods):
        # this is only for non-monographs and the publication must have either a sourcetitle or a made_public_in field
        if not self.is_monograph():
            sourcetitle = self.publication_json["sourcetitle"]
            made_public_in = self.publication_json["made_public_in"]

            if sourcetitle and sourcetitle is not None or made_public_in and made_public_in is not None:
                related_item = ET.SubElement(mods, "relatedItem")
                related_item.set("type", "host")
                if sourcetitle and sourcetitle is not None:
                    title_info = ET.SubElement(related_item, "titleInfo")
                    title = ET.SubElement(title_info, "title")
                    title.text = self.sanitize(sourcetitle)
                if made_public_in and made_public_in is not None:
                    title_info = ET.SubElement(related_item, "titleInfo")
                    title = ET.SubElement(title_info, "title")
                    title.text = self.sanitize(made_public_in)
                # get issn, eissn and isbn if not None and set as identifiers
                issn = self.publication_json["issn"]
                eissn = self.publication_json["eissn"]
                isbn = self.publication_json["isbn"]
                if issn and issn is not None:
                    identifier = ET.SubElement(related_item, "identifier")
                    identifier.set("type", "issn")
                    identifier.text = self.sanitize(issn)
                if eissn and eissn is not None:
                    identifier = ET.SubElement(related_item, "identifier")
                    identifier.set("type", "issn")
                    identifier.text = self.sanitize(eissn)
                if isbn and isbn is not None:
                    identifier = ET.SubElement(related_item, "identifier")
                    identifier.set("type", "isbn")
                    identifier.text = self.sanitize(isbn)
                # if any of sourcevolume, sourceissue, article_number and sourcepages is not None, create a part element an set the values
                sourcevolume = self.publication_json["sourcevolume"]
                sourceissue = self.publication_json["sourceissue"]
                article_number = self.publication_json["article_number"]
                sourcepages = self.publication_json["sourcepages"]
                if sourcevolume and sourcevolume is not None or sourceissue and sourceissue is not None or article_number and article_number is not None or sourcepages and sourcepages is not None:
                    part = ET.SubElement(related_item, "part")
                    if sourcevolume and sourcevolume is not None:
                        detail = ET.SubElement(part, "detail")
                        detail.set("type", "volume")
                        number = ET.SubElement(detail, "number")
                        number.text = self.sanitize(sourcevolume)
                    if sourceissue and sourceissue is not None:
                        detail = ET.SubElement(part, "detail")
                        detail.set("type", "issue")
                        number = ET.SubElement(detail, "number")
                        number.text = self.sanitize(sourceissue)
                    if article_number and article_number is not None:
                        detail = ET.SubElement(part, "detail")
                        detail.set("type", "artNo")
                        number = ET.SubElement(detail, "number")
                        number.text = self.sanitize(article_number)
                    if sourcepages and sourcepages is not None:
                        # if it is possible to split the sourcepages into start and end pages, set the values in the extent element, othervise set the value in the detail (citation attribute) caption element 
                        start_end_pages = self.get_start_and_end_page(sourcepages)
                        if start_end_pages:
                            extent = ET.SubElement(part, "extent")
                            start = ET.SubElement(extent, "start")
                            start.text = start_end_pages[0]
                            end = ET.SubElement(extent, "end")
                            end.text = start_end_pages[1]
                        else:
                            detail = ET.SubElement(part, "detail")
                            detail.set("type", "citation")
                            number = ET.SubElement(detail, "caption")
                            number.text = self.sanitize(sourcepages)

    def get_series(self, mods):
        series = self.publication_json["series"]
        if series and series is not None:
            [self.add_series(mods, serie) for serie in series]
        else:
            []

    def add_series(self, mods, serie):
        title = serie["title"]
        if title and title is not None:
            related_item = ET.SubElement(mods, "relatedItem")
            related_item.set("type", "series")
            title_info = ET.SubElement(related_item, "titleInfo")
            title_element = ET.SubElement(title_info, "title")
            title_element.text = title
            part_number = serie["part"]
            if part_number and part_number is not None:
                part_number_element = ET.SubElement(title_info, "partNumber")
                part_number_element.text = part_number
            issn = serie["issn"]
            if issn and issn is not None:
                identifier = ET.SubElement(related_item, "identifier")
                identifier.set("type", "issn")
                identifier.text = issn

    def get_start_and_end_page(self, sourcepages):
        # if sourcepage contains other than digits, hyphen ("–" or "-") and space, return None
        if not all(c.isdigit() or c in ["–", "-", " "] for c in sourcepages):
            return None
        # split the sourcepages into start and end page if possible
        pages = self.sanitize(sourcepages).replace("–", "-").split("-")
        if len(pages) == 2:
            #trim each page and return the pages if they are not empty
            return [page.strip() for page in pages]
        return None

    def get_location(self, mods):
        files = self.publication_json.get("files")  # Add a check to ensure the "files" key exists
        if files and self.has_viewable_file(files):
            location = ET.SubElement(mods, "location")
            url = ET.SubElement(location, "url")
            url.set("note", "free")
            url.set("usage", "primary")
            url.set("displayLabel", "FULLTEXT")
            url.text = os.environ.get("URI_PREFIX") + "/" + str(self.publication_json["publication_id"])

    def get_physical_description(self, mods):
        files = self.publication_json.get("files")  # Add a check to ensure the "files" key exists
        if files and self.has_viewable_file(files):
            physical_description = ET.SubElement(mods, "physicalDescription")
            form = ET.SubElement(physical_description, "form")
            form.set("authority", "marcform")
            form.text = "electronic"

    def has_viewable_file(self, files):
        # if there is at least one file with following conditions, return True, otherwise return False
        # accepted is not None
        #visible_after is either None or has a date (in format "YYYY-MM-DD") that is before or equal to the current date

        return any(file["accepted"] and (file["visible_after"] is None or datetime.strptime(file["visible_after"], "%Y-%m-%d") <= datetime.now()) for file in files)

    def get_type_of_resource(self, mods):
        publication_type_code = self.publication_json["publication_type_code"]
        type_of_resource = ET.SubElement(mods, "typeOfResource")
        type_of_resource.text = self.get_type_of_resource_code(publication_type_code)

    def get_type_of_resource_code(self, publication_type_code):
        type_of_resource_mapping = {
            'artistic-work_scientific_and_development': "mixed material",
            'artistic-work_original-creative-work': "mixed material"
        }
        return type_of_resource_mapping.get(publication_type_code, "text")

    def sanitize(self, text):
        if text is None:
            return ""
        # remove control characters from the text, except for the newline and cr characters
        return "".join([c for c in text if c.isprintable() or c in ["\n", "\r"]]).strip()

if __name__ == "__main__":   
    if len(sys.argv) < 2:
        print("Please provide a publication id")
        sys.exit()
    else:
        a = OAIProvider()
        pub_id = sys.argv[1]
        print(a.get_oai_data(pub_id))
