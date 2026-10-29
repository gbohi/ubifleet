"""UbiFleet — Pagination personnalisée"""

from rest_framework.pagination import PageNumberPagination


class UbiFleetPagination(PageNumberPagination):
    page_size            = 20
    max_page_size        = 1000
    page_size_query_param = 'page_size'
