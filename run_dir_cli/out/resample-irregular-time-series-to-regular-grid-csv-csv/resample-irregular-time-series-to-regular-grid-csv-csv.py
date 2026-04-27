import pandas as pd
import numpy as np

class TimeResampler:
    """
    Central coordinator for the resampling workflow.
    Handles loading, validation, interpolation, and saving of time series data.
    """

    def _load_data(self, path: str) -> pd.DataFrame:
        """Reads CSV from input_path using pandas."""
        return pd.read_csv(path)

    def _validate(self, df: pd.DataFrame) -> None:
        """
        Validates the input DataFrame schema and data constraints.
        Ensures columns 't' and 'v' exist and 't' is strictly increasing.
        """
        if df.empty:
            raise ValueError("Input CSV is empty.")

        if not {'t', 'v'}.issubset(df.columns):
            raise ValueError("Input CSV must contain columns 't' and 'v'.")

        t_values = df['t'].values
        if len(t_values) > 1:
            if np.any(np.diff(t_values) <= 0):
                raise ValueError("Column 't' must be strictly increasing.")

    def _interpolate(self, df: pd.DataFrame, dt: float) -> pd.DataFrame:
        """
        Generates a regular grid from min(t) to max(t) with step dt.
        Interpolates 'v' onto this grid using linear interpolation.
        """
        t_in = df['t'].values
        v_in = df['v'].values

        t_min = t_in[0]
        t_max = t_in[-1]

        # Generate regular grid: t_min, t_min + dt, ... up to <= t_max
        # Using a small epsilon to handle floating point precision for the endpoint
        epsilon = dt * 1e-10
        t_out = np.arange(t_min, t_max + epsilon, dt)

        # Linear interpolation using numpy.interp
        v_interp = np.interp(t_out, t_in, v_in)

        return pd.DataFrame({
            't': t_out,
            'v_interp': v_interp
        })

    def _write_results(self, df: pd.DataFrame, path: str) -> None:
        """Writes the resulting DataFrame to the specified CSV output_path."""
        df.to_csv(path, index=False)

    def run(self, input_path: str, output_path: str, dt: float, seed: int | None = None) -> dict:
        """
        Main workflow execution: Validate -> Load -> Resample -> Save -> Summarize.
        """
        if dt <= 0:
            raise ValueError("Parameter dt must be strictly positive.")

        # Step 1: Read Data
        df_in = self._load_data(input_path)

        # Step 2: Validate Data
        self._validate(df_in)

        # Step 3: Resample / Interpolate
        df_out = self._interpolate(df_in, dt)

        # Step 4: Write Results
        self._write_results(df_out, output_path)

        # Step 5: Create summary
        return {
            'n_in': int(len(df_in)),
            'n_out': int(len(df_out)),
            'dt': float(dt)
        }

def run(input_path: str, output_path: str, dt: float = 0.5, *, seed: int | None = None) -> dict | None:
    """
    Main entry point required by the verification harness.
    Implements the Resample irregular time series to regular grid requirement.
    """
    resampler = TimeResampler()
    # Errors are raised to comply with the 'Do NOT swallow fatal errors' mandate.
    return resampler.run(input_path, output_path, dt, seed=seed)
