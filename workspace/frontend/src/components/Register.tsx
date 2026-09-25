import React, { useState } from 'react';
import { useHistory } from 'react-router-dom';
import { toast } from 'react-toastify';
import { registerUser } from '../../api';

const Register: React.FC = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [role, setRole] = useState('user');
    const [loading, setLoading] = useState(false);
    const history = useHistory();

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await registerUser(email, password, role);
            if (res.success) {
                toast.success('Registration successful!');
                history.push('/login');
            } else {
                toast.error(res.message || 'Registration failed');
            }
        } catch (error) {
            console.error(error);
            toast.error('An unexpected error occurred');
        } finally {
            setLoading(false);
        }
    };

    return (
        <form onSubmit={handleRegister}>
            <div>
                <label>Email:</label>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div>
                <label>Password:</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <div>
                <label>Role:</label>
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                </select>
            </div>
            <button type="submit" disabled={loading}>
                {loading ? 'Registering...' : 'Register'}
            </button>
        </form>
    );
};

export default Register;
