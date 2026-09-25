import axios from 'axios';

const API_URL = 'http://localhost:8000/api/auth/';

export const registerUser = async (email: string, password: string, role: string) => {
    try {
        const response = await axios.post(`${API_URL}register/`, { email, password, role });
        return { success: true, data: response.data };
    } catch (error) {
        return { success: false, message: error.response?.data?.detail || 'Failed to register' };
    }
};

export const loginUser = async (email: string, password: string) => {
    try {
        const response = await axios.post(`${API_URL}login/`, { email, password });
        localStorage.setItem('access_token', response.data.token);
        return { success: true, data: response.data };
    } catch (error) {
        return { success: false, message: error.response?.data?.error || 'Failed to login' };
    }
};
