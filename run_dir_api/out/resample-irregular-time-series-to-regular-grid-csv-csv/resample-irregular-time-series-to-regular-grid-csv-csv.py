import numpy as np
import pandas as pd

class CSVReader:
    def read_csv(self, path: str) -> pd.DataFrame:
        return pd.read_csv(path)

class CSVWriter:
    def write_csv(self, path: str, data: pd.DataFrame):
        data.to_csv(path, index=False)

class TimeGrid:
    def create_regular_grid(self, min_t: float, max_t: float, dt: float) -> np.ndarray:
        return np.arange(min_t, max_t + dt, dt)

class Interpolator:
    def linear_interpolation(self, t: np.ndarray, v: np.ndarray, t_new: np.ndarray) -> np.ndarray:
        v_interp = np.interp(t_new, t, v)
        if not np.isfinite(v_interp).all():
            raise ValueError("Interpolated values contain NaNs.")
        return v_interp

class Resampler:
    def __init__(self, input_path: str, output_path: str, dt: float = 0.5, *, seed: int | None = None):
        self.input_path = input_path
        self.output_path = output_path
        self.dt = dt
        self.seed = seed
        self.csv_reader = CSVReader()
        self.csv_writer = CSVWriter()
        self.time_grid = TimeGrid()
        self.interpolator = Interpolator()

    def run(self) -> dict | None:
        self.validate_inputs()
        self.schema_contract_validation()
        data = self.preprocess()
        t_new, v_interp = self.compute(data)
        self.postprocess(t_new, v_interp)
        self.write_outputs(t_new, v_interp)
        return self.return_summary_dict(data, t_new)

    def validate_inputs(self):
        if self.dt <= 0:
            raise ValueError("Parameter dt must be greater than 0.")

    def schema_contract_validation(self):
        # This is a simple check; more complex schema validation can be added if needed.
        pass

    def preprocess(self) -> pd.DataFrame:
        data = self.csv_reader.read_csv(self.input_path)
        if data.empty:
            raise ValueError("Input CSV file is empty.")
        if not data['t'].is_monotonic_increasing:
            raise ValueError("Time stamps in the input CSV must be strictly increasing.")
        return data

    def compute(self, data: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        t = data['t'].to_numpy()
        v = data['v'].to_numpy()
        t_new = self.time_grid.create_regular_grid(t.min(), t.max(), self.dt)
        v_interp = self.interpolator.linear_interpolation(t, v, t_new)
        return t_new, v_interp

    def postprocess(self, t_new: np.ndarray, v_interp: np.ndarray):
        # Any post-processing steps can be added here if needed.
        pass

    def write_outputs(self, t_new: np.ndarray, v_interp: np.ndarray):
        output_data = pd.DataFrame({'t': t_new, 'v_interp': v_interp})
        self.csv_writer.write_csv(self.output_path, output_data)

    def return_summary_dict(self, data: pd.DataFrame, t_new: np.ndarray) -> dict:
        return {
            'n_in': len(data),
            'n_out': len(t_new),
            'dt': self.dt
        }

def run(input_path: str, output_path: str, dt: float = 0.5, *, seed: int | None = None) -> dict | None:
    resampler = Resampler(input_path, output_path, dt, seed=seed)
    return resampler.run()
