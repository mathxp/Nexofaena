from django.core.exceptions import ValidationError

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from nexofaena.permissions import IsBodeguero
from nexofaena.services.despacho_rapido_service import DespachoRapidoService


class DespachoRapidoView(APIView):
    permission_classes = [IsBodeguero]

    def post(self, request):
        try:
            movimiento = DespachoRapidoService.despachar(
                inventario_id=request.data.get("inventario"),
                cantidad=request.data.get("cantidad", 1),
                usuario=request.user,
                bodega_id=request.data.get("bodega"),
            )
        except ValidationError as e:
            return Response({"detail": " ".join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "success": True,
                "message": f"Despacho registrado: {movimiento.cantidad} unidad(es) de {movimiento.inventario.nombre}.",
                "data": {
                    "id": movimiento.id,
                    "inventario": movimiento.inventario_id,
                    "producto_nombre": movimiento.inventario.nombre,
                    "cantidad": movimiento.cantidad,
                    "stock_actual": movimiento.stock_actual,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class DespachoRapidoStatsView(APIView):
    permission_classes = [IsBodeguero]

    def get(self, request):
        bodega_id = request.GET.get("bodega")
        return Response(DespachoRapidoService.obtener_estadisticas(bodega_id))
