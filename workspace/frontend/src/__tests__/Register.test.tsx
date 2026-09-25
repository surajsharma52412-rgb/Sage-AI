import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Register from '../components/Register';
import { registerUser } from '../api/auth';

jest.mock('../api/auth');

describe('Register Component', () => {
    it('renders correctly', () => {
        render(
            <MemoryRouter>
                <Register />
            </MemoryRouter>
        );

        expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();
        expect(screen.getByText(/Register/i)).toBeInTheDocument();
    });

    it('submits form successfully', async () => {
        (registerUser as jest.Mock).mockResolvedValue({ success: true, message: 'Registration successful!' });

        render(
            <MemoryRouter>
                <Register />
            </MemoryRouter>
        );

        fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'test@example.com' } });
        fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'testpassword' } });
        fireEvent.click(screen.getByText(/Register/i));

        await waitFor(() => {
            expect(registerUser).toHaveBeenCalledWith('test@example.com', 'testpassword', 'student');
            expect(screen.getByText(/Registration successful!/i)).toBeInTheDocument();
        });
    });

    it('handles registration failure', async () => {
        (registerUser as jest.Mock).mockResolvedValue({ success: false, message: 'Registration failed!' });

        render(
            <MemoryRouter>
                <Register />
            </MemoryRouter>
        );

        fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'test@example.com' } });
        fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'testpassword' } });
        fireEvent.click(screen.getByText(/Register/i));

        await waitFor(() => {
            expect(registerUser).toHaveBeenCalledWith('test@example.com', 'testpassword', 'student');
            expect(screen.getByText(/Registration failed!/i)).toBeInTheDocument();
        });
    });

    it('handles unexpected error', async () => {
        (registerUser as jest.Mock).mockRejectedValue(new Error('Unexpected error'));

        render(
            <MemoryRouter>
                <Register />
            </MemoryRouter>
        );

        fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'test@example.com' } });
        fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'testpassword' } });
        fireEvent.click(screen.getByText(/Register/i));

        await waitFor(() => {
            expect(registerUser).toHaveBeenCalledWith('test@example.com', 'testpassword', 'student');
            expect(screen.getByText(/An unexpected error occurred/i)).toBeInTheDocument();
        });
    });
});
