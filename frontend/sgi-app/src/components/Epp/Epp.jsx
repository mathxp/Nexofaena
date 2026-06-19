import { useState, useEffect } from 'react';
import { FaEdit, FaTrashAlt, FaPlus, FaHardHat } from 'react-icons/fa';
import api from '../../api';
import './Epp.css';

const Epp = () => {
    const [epps, setEpps] = useState([]);
    const [error, setError] = useState('');
    const [modoEdicion, setModoEdicion] = useState(false);
    const [idEdicion, setIdEdicion] = useState(null);
    const [formData, setFormData] = useState({
        codigo: '', nombre: '', categoria: '', unidad_medida: '', stock_minimo: 0, stock_actual: 0
    });

    useEffect(() => { cargarEpps(); }, []);

    const cargarEpps = async () => {
        try {
            const response = await api.get('/epps/');
            setEpps(response.data);
        } catch (err) { setError('Error al cargar EPPs.'); }
    };

    const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            if (modoEdicion) await api.put(`/epps/${idEdicion}/`, formData);
            else await api.post('/epps/', formData);
            limpiarFormulario();
            cargarEpps();
        } catch (err) { setError('Error al guardar. Verifica el código.'); }
    };

    const cargarParaEdicion = (eppItem) => {
        setModoEdicion(true);
        setIdEdicion(eppItem.id);
        setFormData({ ...eppItem });
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const eliminarEpp = async (id) => {
        if (window.confirm("¿Eliminar este EPP?")) {
            try {
                await api.delete(`/epps/${id}/`);
                cargarEpps();
            } catch (err) { setError('No se puede eliminar. Tiene entregas asociadas.'); }
        }
    };

    const limpiarFormulario = () => {
        setModoEdicion(false);
        setIdEdicion(null);
        setFormData({ codigo: '', nombre: '', categoria: '', unidad_medida: '', stock_minimo: 0, stock_actual: 0 });
        setError('');
    };

    return (
        <div className="epp-wrapper">
            <h1 className="page-title"><FaHardHat /> Catálogo de EPP</h1>
            
            {error && <div style={{background: '#fef2f2', color: '#dc2626', padding: '12px', borderRadius: '8px', marginBottom: '20px', fontWeight: '700'}}>{error}</div>}

            <div className="form-card">
                <div className="form-header"><FaPlus /> {modoEdicion ? 'Editar Registro' : 'Registrar Nuevo EPP'}</div>
                <form onSubmit={handleSubmit} className="grid-form">
                    <div className="input-group"><label className="input-label">Código</label><input className="form-input" name="codigo" value={formData.codigo} onChange={handleChange} required disabled={modoEdicion} /></div>
                    <div className="input-group"><label className="input-label">Nombre</label><input className="form-input" name="nombre" value={formData.nombre} onChange={handleChange} required /></div>
                    <div className="input-group"><label className="input-label">Categoría</label><input className="form-input" name="categoria" value={formData.categoria} onChange={handleChange} /></div>
                    <div className="input-group"><label className="input-label">Unidad</label><input className="form-input" name="unidad_medida" value={formData.unidad_medida} onChange={handleChange} required /></div>
                    <div className="input-group"><label className="input-label">Stock Actual</label><input className="form-input" type="number" name="stock_actual" value={formData.stock_actual} onChange={handleChange} required disabled={modoEdicion} /></div>
                    <div className="input-group"><label className="input-label">Stock Mínimo</label><input className="form-input" type="number" name="stock_minimo" value={formData.stock_minimo} onChange={handleChange} required /></div>
                    
                    <div className="btn-group">
                        <button type="submit" className="btn-save">{modoEdicion ? 'Actualizar' : 'Guardar'}</button>
                        {modoEdicion && <button type="button" onClick={limpiarFormulario} className="btn-cancel">Cancelar</button>}
                    </div>
                </form>
            </div>

            <div className="table-wrapper">
                <table className="epp-table">
                    <thead>
                        <tr><th>Código</th><th>Nombre</th><th>Stock</th><th>Acciones</th></tr>
                    </thead>
                    <tbody>
                        {epps.map((eppItem) => (
                            <tr key={eppItem.id}>
                                <td><strong>{eppItem.codigo}</strong></td>
                                <td>{eppItem.nombre}</td>
                                <td>
                                    <span style={{ color: eppItem.stock_actual <= eppItem.stock_minimo ? '#dc2626' : '#059669', fontWeight: '800' }}>
                                        {eppItem.stock_actual}
                                    </span>
                                </td>
                                <td>
                                    <div className="action-box">
                                        <button onClick={() => cargarParaEdicion(eppItem)} className="btn-action btn-edit"><FaEdit /></button>
                                        <button onClick={() => eliminarEpp(eppItem.id)} className="btn-action btn-delete"><FaTrashAlt /></button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default Epp;