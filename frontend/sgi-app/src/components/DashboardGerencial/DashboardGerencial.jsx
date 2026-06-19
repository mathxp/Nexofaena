import { useState, useEffect } from 'react';
import { 
    FaUserFriends, FaBoxOpen, FaChartLine, 
    FaCircle, FaArrowUp, FaChartBar, FaExclamationTriangle, FaBrain 
} from 'react-icons/fa';
import { 
    Chart as ChartJS, CategoryScale, LinearScale, BarElement, 
    PointElement, LineElement, Title, Tooltip, Legend, Filler 
} from 'chart.js';
import { Bar, Line } from 'react-chartjs-2';
import api from '../../api';
import './DashboardGerencial.css'; // CORRECCIÓN: Ruta al mismo nivel

// Registrar componentes de Chart.js
ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, LineElement, Title, Tooltip, Legend, Filler);

const DashboardGerencial = () => {
    // --- ESTADOS DE DATOS REALES ---
    const [kpis, setKpis] = useState({ trabajadores: 0, entregas: 0, consumo: 0 });
    const [prediccionSiguienteMes, setPrediccionSiguienteMes] = useState(0);

    // Estados para Gráficos
    const [labelsMeses, setLabelsMeses] = useState(['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun']);
    const [historicoEntregas, setHistoricoEntregas] = useState([0, 0, 0, 0, 0, 0]);
    const [historicoCriticas, setHistoricoCriticas] = useState([0, 0, 0, 0, 0, 0]);
    const [historicoBajas, setHistoricoBajas] = useState([0, 0, 0, 0, 0, 0]);
    
    const [topConsumoNombres, setTopConsumoNombres] = useState(['Cargando...']);
    const [topConsumoValores, setTopConsumoValores] = useState([0]);

    useEffect(() => {
        cargarYProcesarDatos();
    }, []);

    const cargarYProcesarDatos = async () => {
        try {
            // Traemos TODA la información de Django al mismo tiempo
            const [resTrabajadores, resEntregas, resInventario, resAlertas, resDetalles] = await Promise.all([
                api.get('/trabajadores/').catch(() => ({ data: [] })),
                api.get('/entregas-epp/').catch(() => ({ data: [] })),
                api.get('/inventario/').catch(() => ({ data: [] })),
                api.get('/alertas/').catch(() => ({ data: [] })),
                api.get('/detalles-entrega/').catch(() => ({ data: [] }))
            ]);

            const trabajadores = resTrabajadores.data;
            const entregas = resEntregas.data;
            const inventario = resInventario.data;
            const alertas = resAlertas.data;
            const detalles = resDetalles.data;

            // --- 1. LÓGICA DE TIEMPO (Últimos 6 meses dinámicos) ---
            const hoy = new Date();
            const mesesArray = [];
            const entregasArray = [0, 0, 0, 0, 0, 0];
            const criticasArray = [0, 0, 0, 0, 0, 0];
            const bajasArray = [0, 0, 0, 0, 0, 0];

            for (let i = 5; i >= 0; i--) {
                const fecha = new Date(hoy.getFullYear(), hoy.getMonth() - i, 1);
                let mesStr = fecha.toLocaleString('es-ES', { month: 'short' }).replace('.', '');
                mesStr = mesStr.charAt(0).toUpperCase() + mesStr.slice(1);
                mesesArray.push(mesStr);
            }
            setLabelsMeses(mesesArray);

            // --- 2. PROCESAR KPIs ---
            let entregasMesActual = 0;
            entregas.forEach(e => {
                if (!e.fecha_entrega) return;
                const f = new Date(e.fecha_entrega);
                const diffMeses = (hoy.getFullYear() - f.getFullYear()) * 12 + (hoy.getMonth() - f.getMonth());
                
                if (diffMeses === 0) entregasMesActual++;

                if (diffMeses >= 0 && diffMeses <= 5) {
                    const index = 5 - diffMeses; 
                    entregasArray[index] += 1;
                }
            });

            // Procesar Consumo del Mes
            let consumoMesActual = 0;
            const mapaConsumoGlobal = {};

            detalles.forEach(d => {
                const cantidad = parseFloat(d.cantidad || 0);
                consumoMesActual += cantidad;

                const itemInv = inventario.find(i => i.id === d.epp);
                const nombreItem = itemInv ? itemInv.nombre : `Ítem #${d.epp}`;
                
                mapaConsumoGlobal[nombreItem] = (mapaConsumoGlobal[nombreItem] || 0) + cantidad;
            });

            setKpis({ 
                trabajadores: trabajadores.length, 
                entregas: entregasMesActual, 
                consumo: consumoMesActual 
            });
            setHistoricoEntregas(entregasArray);
            calcularProyeccion(entregasArray);

            // --- 3. PROCESAR TOP 5 CONSUMO ---
            const topConsumo = Object.entries(mapaConsumoGlobal)
                .sort((a, b) => b[1] - a[1]) 
                .slice(0, 5); 
            
            if (topConsumo.length > 0) {
                setTopConsumoNombres(topConsumo.map(item => item[0]));
                setTopConsumoValores(topConsumo.map(item => item[1]));
            }

            // --- 4. PROCESAR ALERTAS ---
            alertas.forEach(a => {
                if (!a.fecha_alerta) return;
                const f = new Date(a.fecha_alerta);
                const diffMeses = (hoy.getFullYear() - f.getFullYear()) * 12 + (hoy.getMonth() - f.getMonth());
                
                if (diffMeses >= 0 && diffMeses <= 5) {
                    const index = 5 - diffMeses;
                    if (a.tipo_alerta === 'CRÍTICA' || a.tipo_alerta === 'QUIEBRE') {
                        criticasArray[index] += 1;
                    } else {
                        bajasArray[index] += 1;
                    }
                }
            });
            
            setHistoricoCriticas(criticasArray);
            setHistoricoBajas(bajasArray);

        } catch (error) {
            console.error("Error agrupando los datos del Dashboard Gerencial:", error);
        }
    };

    // --- 🧠 MOTOR MATEMÁTICO: REGRESIÓN LINEAL ---
    const calcularProyeccion = (dataY) => {
        const n = dataY.length;
        if (n === 0) return setPrediccionSiguienteMes(0);

        let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
        
        dataY.forEach((y, x) => {
            sumX += x;
            sumY += y;
            sumXY += x * y;
            sumXX += x * x;
        });

        const m = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
        const b = (sumY - m * sumX) / n;
        
        const prediccion = Math.max(0, Math.round(m * n + b)); 
        setPrediccionSiguienteMes(prediccion);
    };

    // --- CONFIGURACIÓN DE GRÁFICOS ---
    ChartJS.defaults.color = '#94a3b8'; // Texto gris soft global para los gráficos

    const chartDataEntregas = {
        labels: labelsMeses,
        datasets: [{
            label: 'Entregas',
            data: historicoEntregas,
            backgroundColor: '#ea580c', // Acento Naranja
            borderRadius: 4,
            barThickness: 30,
        }]
    };

    const chartOptionsEntregas = {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { 
            y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.08)', borderDash: [2, 2] } }, 
            x: { grid: { display: false } } 
        }
    };

    const chartDataConsumo = {
        labels: topConsumoNombres,
        datasets: [{
            label: 'Ítems Consumidos',
            data: topConsumoValores,
            backgroundColor: '#fb923c', // Naranja más claro
            borderRadius: 4,
            indexAxis: 'y',
        }]
    };

    const chartOptionsConsumo = {
        responsive: true, maintainAspectRatio: false, indexAxis: 'y',
        plugins: { legend: { display: false } },
        scales: { 
            x: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.08)', borderDash: [2, 2] } }, 
            y: { grid: { display: false } } 
        }
    };

    const chartDataAlertas = {
        labels: labelsMeses,
        datasets: [
            {
                label: 'Crítico',
                data: historicoCriticas,
                borderColor: '#ef4444', // Rojo
                backgroundColor: 'rgba(239, 68, 68, 0.2)',
                fill: true,
                tension: 0.4
            },
            {
                label: 'Bajo',
                data: historicoBajas,
                borderColor: '#eab308', // Amarillo oscuro
                backgroundColor: 'rgba(234, 179, 8, 0.2)',
                fill: true,
                tension: 0.4
            }
        ]
    };

    const chartOptionsAlertas = {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'top', align: 'end', labels: { boxWidth: 10, usePointStyle: true } } },
        scales: { 
            y: { stacked: false, beginAtZero: true, grid: { color: 'rgba(255,255,255,0.08)' } }, 
            x: { grid: { display: false } } 
        }
    };

    return (
        <div className="gerencial-wrapper">
            {/* HEADER GERENCIAL */}
            <div className="gerencial-header">
                <div className="title-container">
                    <h1 className="page-title">DASHBOARD GERENCIAL - BODEGA</h1>
                    <p className="page-subtitle">Jefaturas y Administración</p>
                </div>
                <div className="status-badge">
                    <FaCircle className="status-dot" /> CONECTADO
                </div>
            </div>

            {/* KPIs PRINCIPALES */}
            <div className="kpi-gerencial-grid">
                <div className="kpi-gerencial-card kpi-border-blue">
                    <div className="kpi-header"><FaUserFriends className="icon-blue"/> Trabajadores Activos</div>
                    <h2 className="kpi-value">{kpis.trabajadores}</h2>
                    <div className="kpi-trend trend-neutral">Métricas en vivo</div>
                </div>

                <div className="kpi-gerencial-card kpi-border-orange">
                    <div className="kpi-header"><FaBoxOpen className="icon-orange"/> Entregas Totales (Mes Actual)</div>
                    <h2 className="kpi-value">{kpis.entregas.toLocaleString()} <span className="kpi-unit">ítems</span></h2>
                    <div className="kpi-trend trend-up"><FaArrowUp /> Flujo detectado</div>
                </div>

                <div className="kpi-gerencial-card kpi-border-green">
                    <div className="kpi-header"><FaChartLine className="icon-green"/> Consumo Global Registrado</div>
                    <h2 className="kpi-value">{kpis.consumo.toLocaleString()} <span className="kpi-unit">ítems</span></h2>
                    <div className="kpi-trend trend-green">✔ Sincronizado con API</div>
                </div>
            </div>

            {/* GRÁFICOS */}
            <div className="charts-grid">
                
                <div className="chart-card">
                    <div className="chart-header-ui">
                        <div className="chart-title"><FaChartBar className="icon-orange"/> Entregas de EPP por Mes</div>
                        <div className="chart-subtitle">(Últimos 6 Meses)</div>
                    </div>
                    <div className="chart-container">
                        <Bar data={chartDataEntregas} options={chartOptionsEntregas} />
                    </div>
                    <div className="prediction-box">
                        <FaBrain className="icon-brain"/> 
                        <span>Proyección IA: Se estiman <strong>{prediccionSiguienteMes}</strong> entregas para el próximo mes.</span>
                    </div>
                </div>

                <div className="chart-card">
                    <div className="chart-header-ui">
                        <div className="chart-title"><FaBoxOpen className="icon-orange"/> Consumo de Materiales</div>
                        <div className="chart-subtitle">(Top 5 Ítems Reales)</div>
                    </div>
                    <div className="chart-container">
                        <Bar data={chartDataConsumo} options={chartOptionsConsumo} />
                    </div>
                </div>

                <div className="chart-card full-width">
                    <div className="chart-header-ui">
                        <div className="chart-title"><FaExclamationTriangle className="icon-orange"/> Historial de Alertas Generadas</div>
                        <div className="chart-subtitle">(Últimos 6 Meses)</div>
                    </div>
                    <div className="chart-container">
                        <Line data={chartDataAlertas} options={chartOptionsAlertas} />
                    </div>
                </div>

            </div>
        </div>
    );
};

export default DashboardGerencial;