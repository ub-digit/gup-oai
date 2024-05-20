from oai_repo import DataInterface, Identify, MetadataFormat, RecordHeader, Set
from elasticsearch import Elasticsearch
import os
from datetime import datetime,timezone
import oai
import lxml
import lxml.etree as ET
class GUPProvider(DataInterface):
    def __init__(self):
        self.index = 'publications'
        self.es = Elasticsearch(hosts=[{'host': os.environ['ES_HOST_NAME'], 'port': 9200, 'scheme': 'http'}])
        self.limit = int(os.environ['COUNT'])
        self.provider = oai.OAIProvider()

    def get_identify(self) -> Identify:
        ident = Identify()
        ident.repository_name = os.environ['REPOSITORY_NAME']
        ident.base_url = os.environ['BASE_URL']
        ident.granularity = 'YYYY-MM-DDThh:mm:ssZ'
        ident.admin_email = [os.environ['ADMIN_EMAIL']]
        ident.deleted_record = 'transient'
        ident.earliest_datestamp = '1950-10-01T00:00:00Z'
        return ident

    def get_record_metadata(self, identifier: str, metadata_prefix: str) -> lxml.etree._Element:
        internal_identifier = self.get_internal_identifier(identifier)
        if self.es.exists(index="publications", id=internal_identifier):
            publication = self.es.get(index="publications", id=internal_identifier)
            metadata = self.provider.get_oai_data(publication)
            return metadata
        else:
            raise OAIErrorIdDoesNotExist("The given identifier does not exist.")

    def get_record_header(self, identifier: str) -> RecordHeader:
        internal_identifier = self.get_internal_identifier(identifier)
        if self.es.exists(index="publications", id=internal_identifier):
            publication = self.es.get(index="publications", id=internal_identifier)
            header = self.provider.build_recordheader(publication['_source'])
            return header
        else:
            raise OAIErrorIdDoesNotExist("The given identifier does not exist.")

    def get_record_abouts(self, identifier: str) -> list:
        return []

    def is_valid_identifier(self, identifier: str) -> bool:
        internal_identifier = self.get_internal_identifier(identifier)
        # Check if the record exists in the index
        res = self.es.exists(index=self.index, id=internal_identifier)
        return res

    def get_internal_identifier(self, identifier: str) -> str:
        # Transform an OAI identifier to a valid internal identifier (gup_*)
        return identifier.replace(os.environ.get("IDENTIFIER_PREFIX") + "/", "gup_")

    def list_set_specs(self, identifier: str=None, cursor: int=0) -> tuple:
        return ['gu'], None, None

    def get_set(self, setspec: str) -> Set:
        set = Set()
        if setspec == 'gu':
            set.spec = 'gu'
            set.name = 'Göteborgs universitet'
            description = ET.Element("description")
            description.text = "Publications affiliated with Göteborgs universitet"
            set.description = [description]
        else:
            raise OAIErrorNoSetHierarchy("Unknown set")
        return set


    def get_metadata_formats(self, identifier = None) -> list:
#        formats = ['oai_dc', 'mods']
        formats = ['mods']
        # Build metadata format object for each element
        return [self.build_metadata_format_object(format) for format in formats]

    def list_identifiers(self, metadata_prefix: str, from_date: str, until_date: str, set=None, cursor = 0) -> tuple:
        # filter datestamp by from_date and until_date if provided
        # Create a base query
        # Filter source by 'gup'
        query = {
            'query': {
                'bool': {
                    'must': [
                        {
                            'term': {
                                'source': 'gup'
                            }
                        }
                    ]
                }
            },
            'sort': [
                {
                    'publication_id': {
                        'order': 'asc'
                    }
                }
            ],
            'from': cursor,
            'size': self.limit,
            'track_total_hits': True
        }

        query = self.add_set_to_query(query, set)

        if from_date is None and until_date is None:
            query = query
        elif from_date is None:
            query = self.set_datestamp_until_open(query, until_date)
        elif until_date is None:
            query = self.set_datestamp_from_open(query, from_date)
        else:
            query = self.set_datestamp_closed(query, from_date, until_date)


        results = self.get_records_from_index(query)

        list_of_identifiers = []
        for result in results[0]:
            list_of_identifiers.append(result['_source']['id'])

        total_size = results[1]
        return (list_of_identifiers, total_size, None)

    def add_set_to_query(self, query, set):
        # Filter by set if provided (only 'gu' is supported so far)
        if set is not None and set == 'gu':
            query['query']['bool']['must'].append({
                'term': {
                    'affiliated': True
                }
            })
        return query

    def get_records_from_index(self, query) -> tuple:
        results = self.es.search(index=self.index, body=query)
        return (results['hits']['hits'], results['hits']['total']['value'])


    def set_datestamp_from_open(self, query, from_date: str) -> tuple:
        # Filter datestamp by from_date
        query['query']['bool']['must'].append({
            'range': {
                'updated_at': {
                    'gte': from_date
                }
            }
        })
        return query

    def set_datestamp_until_open(self, query, until_date: str) -> tuple:
        # Filter datestamp by until_date
        query['query']['bool']['must'].append({
            'range': {
                'updated_at': {
                    'lte': until_date
                }
            }
        })
        return query

    def set_datestamp_closed(self, query, from_date: str, until_date: str) -> tuple:
        # Filter datestamp by from_date and until_date if provided
        query['query']['bool']['must'].append({
            'range': {
                'updated_at': {
                    'gte': from_date,
                    'lte': until_date
                }
            }
        })
        return query

    def build_metadata_format_object(self, metadata_prefix: str) -> str:
        if metadata_prefix == 'oai_dc':
            return MetadataFormat(
                "oai_dc",
                "http://www.openarchives.org/OAI/2.0/oai_dc.xsd",
                "http://www.openarchives.org/OAI/2.0/oai_dc/"
            )
        elif metadata_prefix == 'mods':
            return MetadataFormat(
                "mods",
                "http://www.loc.gov/standards/mods/v3/mods-3-7.xsd",
                "http://www.loc.gov/mods/v3"
            )
