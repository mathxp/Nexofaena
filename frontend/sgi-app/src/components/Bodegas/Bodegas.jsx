import { useState, useEffect } from 'react';
import { FaBuilding, FaEdit, FaTrashAlt, FaPlus } from 'react-icons/fa';
import api from '../../api';
import './Bodegas.css';

const Bodegas = () => {
    const [bodegas, setBodegas] = useState([]);
    const [error, setError] = useState('');
    
    const [modoEdicion, setModoEdicion] = useState(false);
    const [idEdicion, setIdEdicion] = useState(null);

    const [formData, setFormData] = useState({ nombre: '', ubicacion: '', responsable: '' });

    useEffect(() => { cargarBodegas(); }, []);

    const cargarBodegas = async () => {
        try {
            const response = await api.get('/bodegas/');
            setBodegas(response.data);
        } catch (err) { setError('Error al cargar la lista de bodegas.'); }
    };

    const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            if (modoEdicion) await api.put(`/bodegas/${idEdicion}/`, formData);
            else await api.post('/bodegas/', formData);
            
            limpiarFormulario();
            cargarBodegas();
        } catch (err) { setError('Error al guardar. Verifica los datos.'); }
    };

    const cargarParaEdicion = (bodega) => {
        setModoEdicion(true);
        setIdEdicion(bodega.id);
        setFormData({ nombre: bodega.nombre, ubicacion: bodega.ubicacion || '', responsable: bodega.responsable || '' });
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const eliminarBodega = async (id) => {
        if (window.confirm("¿Eliminar esta bodega? No podrás si tiene inventario asignado.")) {
            try {
                await api.delete(`/bodegas/${id}/`);
                cargarBodegas();
            } catch (err) { setError('No se puede eliminar. Tiene productos asociados.'); }
        }
    };

    const limpiarFormulario = () => {
        setModoEdicion(false);
        setIdEdicion(null);
        setFormData({ nombre: '', ubicacion: '', responsable: '' });
        setError('');
    };

    return (
        <div className="bodegas-wrapper">
            <h1 className="page-title"><FaBuilding /> Gestión de Bodegas</h1>
            
            {error && <div className="error-message">{error}</div>}

            <div className={`form-container ${modoEdicion ? 'edit-mode' : ''}`}>
                <div className="form-header">
                    <FaPlus /> {modoEdicion ? 'Editar Registro de Bodega' : 'Registrar Nueva Bodega'}
                </div>
                
                <form onSubmit={handleSubmit} className="form-grid">
                    <div className="input-group">
                        <label className="input-label">Nombre</label>
                        <input className="form-input" type="text" name="nombre" placeholder="Ej: Bodega Central" value={formData.nombre} onChange={handleChange} required />
                    </div>
                    <div className="input-group">
                        <label className="input-label">Ubicación</label>
                        <input className="form-input" type="text" name="ubicacion" placeholder="Ej: Sector A" value={formData.ubicacion} onChange={handleChange} />
                    </div>
                    <div className="input-group full-width">
                        <label className="input-label">Responsable</label>
                        <input className="form-input" type="text" name="responsable" placeholder="Ej: Juan Pérez" value={formData.responsable} onChange={handleChange} />
                    </div>
                    
                    <div className="form-actions full-width">
                        <button type="submit" className="btn-guardar">
                            {modoEdicion ? 'Actualizar Bodega' : 'Guardar Bodega'}
                        </button>
                        {modoEdicion && (
                            <button type="button" onClick={limpiarFormulario} className="btn-cancelar">
                                Cancelar
                            </button>
                        )}
                    </div>
                </form>
            </div>

            <div className="table-section">
                <div className="table-responsive">
                    <table className="styled-table">
                        <thead>
                            <tr>
                                <th>Nombre</th>
                                <th>Ubicación</th>
                                <th>Responsable</th>
                                <th>Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            {bodegas.length === 0 ? (
                                <tr>
                                    <td colSpan="4" style={{ textAlign: 'center', padding: '30px', color: '#94a3b8' }}>
                                        No hay bodegas registradas en el sistema.
                                    </td>
                                </tr>
                            ) : (
                                bodegas.map((b) => (
                                    <tr key={b.id}>
                                        <td><strong>{b.nombre}</strong></td>
                                        <td>{b.ubicacion || 'N/A'}</td>
                                        <td>{b.responsable || 'N/A'}</td>
                                        <td>
                                            <div className="action-buttons">
                                                <button onClick={() => cargarParaEdicion(b)} className="btn-icon btn-edit" title="Editar"><FaEdit /></button>
                                                <button onClick={() => eliminarBodega(b.id)} className="btn-icon btn-delete" title="Eliminar"><FaTrashAlt /></button>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default Bodegas;