from rest_framework.response import Response

LIMITE_MAXIMO = 1000


class LimiteListaMixin:
    """
    Agrega ?limite=N al listado: devuelve solo los N primeros registros del
    orden del queryset (los más recientes en movimientos y entregas). Sin el
    parámetro, el listado sigue completo, así que nada existente se rompe.

    Se aplica en list() y no en get_queryset(): un queryset recortado no se
    puede volver a filtrar, y retrieve/update/destroy filtran por id.
    """

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        limite = request.GET.get("limite", "")
        if limite.isdigit() and int(limite) > 0:
            queryset = queryset[:min(int(limite), LIMITE_MAXIMO)]

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
