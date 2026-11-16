// Pro Camera Tracker - bundle adjustment core.
// One C entry point around Ceres Solver (BSD-3-Clause); no other dependencies.
// Camera model: f, cx, cy, k1 (one radial term), shared by all frames.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>

#include <ceres/ceres.h>
#include <ceres/rotation.h>

namespace {

struct Reprojection {
  Reprojection(double x, double y) : x_(x), y_(y) {}
  // pose = (qw, qx, qy, qz, tx, ty, tz): one block per camera keeps the
  // reduced camera system at one block per frame
  template <typename T>
  bool operator()(const T* const pose, const T* const X, const T* const K, T* r) const {
    T p[3];
    ceres::UnitQuaternionRotatePoint(pose, X, p);
    p[0] += pose[4];
    p[1] += pose[5];
    p[2] += pose[6];
    if (p[2] < T(2.220446049250313e-16)) {  // behind the camera: no constraint
      r[0] = T(0);
      r[1] = T(0);
      return true;
    }
    const T u = p[0] / p[2], v = p[1] / p[2];
    const T d = T(1) + K[3] * (u * u + v * v);
    r[0] = K[0] * d * u + K[1] - T(x_);
    r[1] = K[0] * d * v + K[2] - T(y_);
    return true;
  }
  double x_, y_;
};

}  // namespace

extern "C" {

#if defined(_WIN32)
#define PCT_API __declspec(dllexport)
#else
#define PCT_API __attribute__((visibility("default")))
#endif

PCT_API int pct_ba_version() { return 3; }

// Poses: world -> camera, quaternion (w,x,y,z) + translation, updated in place.
// gauge_cam1 / gauge_cam2: camera indices used to fix the gauge (-1 = none);
// gauge_dim: translation axis of camera 2 that is held.
// summary[6] = initial cost, final cost, iterations, termination type,
//              linear solver type, usable (1/0)
// returns 0 = solved, 1 = nothing to solve, 2 = invalid input, 3 = solver failure
PCT_API int pct_ba_solve(int n_cams, double* q, double* t, const unsigned char* cam_fixed,
                         int n_pts, double* X,
                         int n_obs, const int* obs_cam, const int* obs_pt, const double* obs_xy,
                         double* K, int refine_focal, int refine_k1,
                         double loss_scale, int max_iter, double function_tolerance,
                         int gauge_cam1, int gauge_cam2, int gauge_dim,
                         int num_threads, double* summary) {
  if (n_cams <= 0 || n_pts <= 0 || n_obs <= 0) return 1;
  for (int i = 0; i < n_obs; ++i) {
    if (obs_cam[i] < 0 || obs_cam[i] >= n_cams || obs_pt[i] < 0 || obs_pt[i] >= n_pts) return 2;
  }
  ceres::Problem::Options popt;
  popt.loss_function_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;
  popt.manifold_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;
  ceres::CauchyLoss loss(loss_scale > 0 ? loss_scale : 1.0);
  using PoseManifold = ceres::ProductManifold<ceres::QuaternionManifold, ceres::EuclideanManifold<3>>;
  using GaugeManifold = ceres::ProductManifold<ceres::QuaternionManifold, ceres::SubsetManifold>;
  PoseManifold pose_manifold{ceres::QuaternionManifold(), ceres::EuclideanManifold<3>()};
  // gauge (as COLMAP): camera 1 fully fixed, one translation axis of camera 2 fixed
  if (gauge_dim < 0 || gauge_dim > 2) gauge_dim = 0;
  GaugeManifold gauge_manifold{ceres::QuaternionManifold(),
                               ceres::SubsetManifold(3, std::vector<int>{gauge_dim})};
  std::vector<double> pose(static_cast<size_t>(n_cams) * 7);
  for (int c = 0; c < n_cams; ++c) {
    std::copy(q + 4 * c, q + 4 * c + 4, pose.begin() + 7 * c);
    std::copy(t + 3 * c, t + 3 * c + 3, pose.begin() + 7 * c + 4);
  }
  ceres::SubsetManifold* intr = nullptr;
  ceres::Problem problem(popt);

  std::vector<char> cam_used(n_cams, 0), pt_used(n_pts, 0);
  for (int i = 0; i < n_obs; ++i) {
    const int c = obs_cam[i], p = obs_pt[i];
    problem.AddResidualBlock(
        new ceres::AutoDiffCostFunction<Reprojection, 2, 7, 3, 4>(
            new Reprojection(obs_xy[2 * i], obs_xy[2 * i + 1])),
        &loss, pose.data() + 7 * c, X + 3 * p, K);
    cam_used[c] = 1;
    pt_used[p] = 1;
  }
  // cameras
  int n_used = 0;
  for (int c = 0; c < n_cams; ++c) {
    if (!cam_used[c]) continue;
    ++n_used;
    double* pc = pose.data() + 7 * c;
    if ((cam_fixed && cam_fixed[c]) || c == gauge_cam1) {
      problem.SetParameterBlockConstant(pc);
    } else if (c == gauge_cam2) {
      problem.SetManifold(pc, &gauge_manifold);
    } else {
      problem.SetManifold(pc, &pose_manifold);
    }
  }
  // intrinsics: principal point always constant
  std::vector<int> constant = {1, 2};
  if (!refine_focal) constant.push_back(0);
  if (!refine_k1) constant.push_back(3);
  std::sort(constant.begin(), constant.end());
  if (constant.size() == 4) {
    problem.SetParameterBlockConstant(K);
  } else {
    intr = new ceres::SubsetManifold(4, constant);
    problem.SetManifold(K, intr);
  }

  ceres::Solver::Options opt;
  opt.max_num_iterations = max_iter > 0 ? max_iter : 100;
  opt.function_tolerance = function_tolerance;
  opt.gradient_tolerance = 1e-4;
  opt.parameter_tolerance = 0.0;
  opt.max_linear_solver_iterations = 200;
  opt.max_num_consecutive_invalid_steps = 10;
  opt.max_consecutive_nonmonotonic_steps = 10;
  opt.logging_type = ceres::SILENT;
  opt.minimizer_progress_to_stdout = false;
  // eliminate the points first (Schur complement on the cameras)
  auto* ordering = new ceres::ParameterBlockOrdering;
  for (int p = 0; p < n_pts; ++p)
    if (pt_used[p]) ordering->AddElementToGroup(X + 3 * p, 0);
  for (int c = 0; c < n_cams; ++c)
    if (cam_used[c]) ordering->AddElementToGroup(pose.data() + 7 * c, 1);
  ordering->AddElementToGroup(K, 1);
  opt.linear_solver_ordering.reset(ordering);

  const bool lapack =
      ceres::IsDenseLinearAlgebraLibraryTypeAvailable(ceres::LAPACK);
  ceres::SparseLinearAlgebraLibraryType sparse = ceres::NO_SPARSE;
  if (ceres::IsSparseLinearAlgebraLibraryTypeAvailable(ceres::ACCELERATE_SPARSE))
    sparse = ceres::ACCELERATE_SPARSE;
  else if (ceres::IsSparseLinearAlgebraLibraryTypeAvailable(ceres::EIGEN_SPARSE))
    sparse = ceres::EIGEN_SPARSE;
  const int dense_limit = 400;  // cameras: the reduced camera system stays small and dense
  if (n_used <= dense_limit || sparse == ceres::NO_SPARSE) {
    opt.linear_solver_type = ceres::DENSE_SCHUR;
    opt.dense_linear_algebra_library_type = lapack ? ceres::LAPACK : ceres::EIGEN;
  } else if (n_used <= 2000) {
    opt.linear_solver_type = ceres::SPARSE_SCHUR;
    opt.sparse_linear_algebra_library_type = sparse;
  } else {
    opt.linear_solver_type = ceres::ITERATIVE_SCHUR;
    opt.preconditioner_type = ceres::SCHUR_JACOBI;
  }
  int threads = num_threads;
  if (threads <= 0) threads = static_cast<int>(std::thread::hardware_concurrency());
  if (threads <= 0) threads = 1;
  if (problem.NumResiduals() < 50000) threads = 1;  // threading overhead dominates
  opt.num_threads = threads;

  std::string err;
  if (!opt.IsValid(&err)) {
    delete intr;
    return 3;
  }
  ceres::Solver::Summary s;
  ceres::Solve(opt, &problem, &s);
  if (std::getenv("PCT_BA_REPORT")) std::fprintf(stderr, "%s\n", s.FullReport().c_str());
  if (summary) {
    summary[0] = s.initial_cost;
    summary[1] = s.final_cost;
    summary[2] = static_cast<double>(s.iterations.size());
    summary[3] = static_cast<double>(s.termination_type);
    summary[4] = static_cast<double>(opt.linear_solver_type);
    summary[5] = s.IsSolutionUsable() ? 1.0 : 0.0;
  }
  // hand the poses back, quaternions normalised
  for (int c = 0; c < n_cams; ++c) {
    const double* pc = pose.data() + 7 * c;
    double n = std::sqrt(pc[0] * pc[0] + pc[1] * pc[1] + pc[2] * pc[2] + pc[3] * pc[3]);
    if (!(n > 0)) n = 1.0;
    for (int k = 0; k < 4; ++k) q[4 * c + k] = pc[k] / n;
    for (int k = 0; k < 3; ++k) t[3 * c + k] = pc[4 + k];
  }
  delete intr;
  return s.termination_type == ceres::FAILURE ? 3 : 0;
}

}  // extern "C"
