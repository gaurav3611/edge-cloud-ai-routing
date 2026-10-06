# Statistics (mean +/- 95% CI over seeds; paired Wilcoxon signed-rank)

## A. Load sweep (rho=0.8)

- local: slo 0.253, cslo 0.206+/-0.023, bcslo 0.211+/-0.022, viol 0.166, cgoodput 407, dec_us 0.0
- rr: slo 0.678, cslo 0.550+/-0.047, bcslo 0.561+/-0.037, viol 0.195, cgoodput 1078, dec_us 1.5
- rr_g: slo 0.720, cslo 0.574+/-0.033, bcslo 0.582+/-0.023, viol 0.203, cgoodput 1123, dec_us 0.9
- epara: slo 0.883, cslo 0.708+/-0.082, bcslo 0.694+/-0.056, viol 0.200, cgoodput 1391, dec_us 17.3
- epara_priv: slo 0.841, cslo 0.841+/-0.046, bcslo 0.812+/-0.049, viol 0.000, cgoodput 1648, dec_us 30.3
- tera: slo 0.867, cslo 0.867+/-0.060, bcslo 0.841+/-0.043, viol 0.000, cgoodput 1698, dec_us 31.9
- ours: slo 0.812, cslo 0.812+/-0.055, bcslo 0.808+/-0.040, viol 0.000, cgoodput 1590, dec_us 36.7
- cslo epara_priv - epara @rho=0.4: +0.163 +/- 0.020 (p=0.0020, n=10, wins 100%)
- cslo epara_priv - epara @rho=0.6: +0.150 +/- 0.019 (p=0.0020, n=10, wins 100%)
- cslo epara_priv - epara @rho=0.8: +0.133 +/- 0.060 (p=0.0039, n=10, wins 90%)
- cslo epara_priv - epara @rho=0.9: +0.116 +/- 0.072 (p=0.0020, n=10, wins 100%)
- cslo epara_priv - epara @rho=1.0: +0.100 +/- 0.034 (p=0.0020, n=10, wins 100%)
- cslo tera - epara_priv @rho=0.4: +0.001 +/- 0.001 (p=0.1055, n=10, wins 70%)
- cslo tera - epara_priv @rho=0.6: +0.005 +/- 0.006 (p=0.1602, n=10, wins 70%)
- cslo tera - epara_priv @rho=0.8: +0.026 +/- 0.041 (p=0.0645, n=10, wins 90%)
- cslo tera - epara_priv @rho=0.9: +0.004 +/- 0.041 (p=0.8457, n=10, wins 60%)
- cslo tera - epara_priv @rho=1.0: -0.016 +/- 0.031 (p=0.3750, n=10, wins 30%)
- cslo tera - epara @rho=0.4: +0.164 +/- 0.020 (p=0.0020, n=10, wins 100%)
- cslo tera - epara @rho=0.6: +0.155 +/- 0.020 (p=0.0020, n=10, wins 100%)
- cslo tera - epara @rho=0.8: +0.159 +/- 0.074 (p=0.0020, n=10, wins 100%)
- cslo tera - epara @rho=0.9: +0.120 +/- 0.067 (p=0.0020, n=10, wins 100%)
- cslo tera - epara @rho=1.0: +0.084 +/- 0.039 (p=0.0020, n=10, wins 100%)
- cslo tera - rr @rho=0.4: +0.172 +/- 0.017 (p=0.0020, n=10, wins 100%)
- cslo tera - rr @rho=0.6: +0.199 +/- 0.018 (p=0.0020, n=10, wins 100%)
- cslo tera - rr @rho=0.8: +0.317 +/- 0.054 (p=0.0020, n=10, wins 100%)
- cslo tera - rr @rho=0.9: +0.129 +/- 0.061 (p=0.0059, n=10, wins 90%)
- cslo tera - rr @rho=1.0: +0.047 +/- 0.048 (p=0.0840, n=10, wins 80%)
- cslo epara - rr @rho=0.4: +0.008 +/- 0.007 (p=0.0137, n=10, wins 90%)
- cslo epara - rr @rho=0.6: +0.044 +/- 0.014 (p=0.0020, n=10, wins 100%)
- cslo epara - rr @rho=0.8: +0.157 +/- 0.053 (p=0.0020, n=10, wins 100%)
- cslo epara - rr @rho=0.9: +0.009 +/- 0.070 (p=0.9219, n=10, wins 50%)
- cslo epara - rr @rho=1.0: -0.037 +/- 0.041 (p=0.0840, n=10, wins 30%)
- cslo rr_g - rr @rho=0.4: -0.000 +/- 0.006 (p=0.8457, n=10, wins 50%)
- cslo rr_g - rr @rho=0.6: +0.001 +/- 0.013 (p=1.0000, n=10, wins 40%)
- cslo rr_g - rr @rho=0.8: +0.023 +/- 0.033 (p=0.1934, n=10, wins 70%)
- cslo rr_g - rr @rho=0.9: +0.044 +/- 0.031 (p=0.0137, n=10, wins 80%)
- cslo rr_g - rr @rho=1.0: +0.057 +/- 0.035 (p=0.0137, n=10, wins 80%)
- bcslo epara_priv - epara @rho=0.4: +0.165 +/- 0.037 (p=0.0020, n=10, wins 100%)
- bcslo epara_priv - epara @rho=0.6: +0.144 +/- 0.033 (p=0.0020, n=10, wins 100%)
- bcslo epara_priv - epara @rho=0.8: +0.118 +/- 0.030 (p=0.0020, n=10, wins 100%)
- bcslo epara_priv - epara @rho=0.9: +0.126 +/- 0.050 (p=0.0020, n=10, wins 100%)
- bcslo epara_priv - epara @rho=1.0: +0.121 +/- 0.048 (p=0.0039, n=10, wins 90%)
- bcslo tera - epara_priv @rho=0.4: +0.007 +/- 0.009 (p=0.2754, n=10, wins 60%)
- bcslo tera - epara_priv @rho=0.6: +0.008 +/- 0.014 (p=0.4922, n=10, wins 60%)
- bcslo tera - epara_priv @rho=0.8: +0.029 +/- 0.032 (p=0.0645, n=10, wins 80%)
- bcslo tera - epara_priv @rho=0.9: +0.005 +/- 0.035 (p=0.6953, n=10, wins 60%)
- bcslo tera - epara_priv @rho=1.0: -0.007 +/- 0.029 (p=0.5566, n=10, wins 40%)
- bcslo tera - epara @rho=0.4: +0.172 +/- 0.035 (p=0.0020, n=10, wins 100%)
- bcslo tera - epara @rho=0.6: +0.151 +/- 0.027 (p=0.0020, n=10, wins 100%)
- bcslo tera - epara @rho=0.8: +0.147 +/- 0.039 (p=0.0020, n=10, wins 100%)
- bcslo tera - epara @rho=0.9: +0.131 +/- 0.056 (p=0.0020, n=10, wins 100%)
- bcslo tera - epara @rho=1.0: +0.114 +/- 0.044 (p=0.0020, n=10, wins 100%)
- bcslo tera - rr @rho=0.4: +0.205 +/- 0.043 (p=0.0020, n=10, wins 100%)
- bcslo tera - rr @rho=0.6: +0.211 +/- 0.026 (p=0.0020, n=10, wins 100%)
- bcslo tera - rr @rho=0.8: +0.280 +/- 0.037 (p=0.0020, n=10, wins 100%)
- bcslo tera - rr @rho=0.9: +0.157 +/- 0.035 (p=0.0020, n=10, wins 100%)
- bcslo tera - rr @rho=1.0: +0.109 +/- 0.051 (p=0.0039, n=10, wins 90%)
- bcslo epara - rr @rho=0.4: +0.034 +/- 0.028 (p=0.0195, n=10, wins 90%)
- bcslo epara - rr @rho=0.6: +0.060 +/- 0.017 (p=0.0020, n=10, wins 100%)
- bcslo epara - rr @rho=0.8: +0.132 +/- 0.034 (p=0.0020, n=10, wins 100%)
- bcslo epara - rr @rho=0.9: +0.026 +/- 0.048 (p=0.4316, n=10, wins 50%)
- bcslo epara - rr @rho=1.0: -0.005 +/- 0.039 (p=0.9219, n=10, wins 50%)
- bcslo rr_g - rr @rho=0.4: +0.016 +/- 0.035 (p=0.3223, n=10, wins 60%)
- bcslo rr_g - rr @rho=0.6: -0.007 +/- 0.019 (p=0.4316, n=10, wins 50%)
- bcslo rr_g - rr @rho=0.8: +0.021 +/- 0.039 (p=0.4316, n=10, wins 60%)
- bcslo rr_g - rr @rho=0.9: +0.018 +/- 0.019 (p=0.0840, n=10, wins 70%)
- bcslo rr_g - rr @rho=1.0: +0.030 +/- 0.030 (p=0.0840, n=10, wins 80%)
- slo epara_priv - epara @rho=0.4: -0.014 +/- 0.013 (p=0.0039, n=10, wins 10%)
- slo epara_priv - epara @rho=0.6: -0.037 +/- 0.015 (p=0.0020, n=10, wins 0%)
- slo epara_priv - epara @rho=0.8: -0.043 +/- 0.083 (p=0.3223, n=10, wins 20%)
- slo epara_priv - epara @rho=0.9: +0.031 +/- 0.077 (p=0.7695, n=10, wins 50%)
- slo epara_priv - epara @rho=1.0: +0.053 +/- 0.040 (p=0.0195, n=10, wins 80%)
- slo tera - epara_priv @rho=0.4: +0.001 +/- 0.001 (p=0.1055, n=10, wins 70%)
- slo tera - epara_priv @rho=0.6: +0.005 +/- 0.006 (p=0.1602, n=10, wins 70%)
- slo tera - epara_priv @rho=0.8: +0.026 +/- 0.041 (p=0.0645, n=10, wins 90%)
- slo tera - epara_priv @rho=0.9: +0.004 +/- 0.041 (p=0.8457, n=10, wins 60%)
- slo tera - epara_priv @rho=1.0: -0.016 +/- 0.031 (p=0.3750, n=10, wins 30%)
- slo tera - epara @rho=0.4: -0.013 +/- 0.013 (p=0.0020, n=10, wins 0%)
- slo tera - epara @rho=0.6: -0.032 +/- 0.015 (p=0.0020, n=10, wins 0%)
- slo tera - epara @rho=0.8: -0.017 +/- 0.090 (p=0.2754, n=10, wins 20%)
- slo tera - epara @rho=0.9: +0.036 +/- 0.071 (p=0.3750, n=10, wins 60%)
- slo tera - epara @rho=1.0: +0.037 +/- 0.040 (p=0.0840, n=10, wins 70%)
- slo tera - rr @rho=0.4: -0.005 +/- 0.011 (p=0.5566, n=10, wins 40%)
- slo tera - rr @rho=0.6: +0.018 +/- 0.015 (p=0.0488, n=10, wins 90%)
- slo tera - rr @rho=0.8: +0.188 +/- 0.057 (p=0.0020, n=10, wins 100%)
- slo tera - rr @rho=0.9: +0.047 +/- 0.054 (p=0.1309, n=10, wins 80%)
- slo tera - rr @rho=1.0: -0.008 +/- 0.042 (p=0.9219, n=10, wins 40%)
- slo epara - rr @rho=0.4: +0.008 +/- 0.005 (p=0.0020, n=10, wins 100%)
- slo epara - rr @rho=0.6: +0.050 +/- 0.016 (p=0.0020, n=10, wins 100%)
- slo epara - rr @rho=0.8: +0.205 +/- 0.068 (p=0.0020, n=10, wins 100%)
- slo epara - rr @rho=0.9: +0.011 +/- 0.085 (p=1.0000, n=10, wins 50%)
- slo epara - rr @rho=1.0: -0.045 +/- 0.047 (p=0.0645, n=10, wins 30%)
- slo rr_g - rr @rho=0.4: -0.001 +/- 0.002 (p=0.1055, n=10, wins 20%)
- slo rr_g - rr @rho=0.6: +0.006 +/- 0.008 (p=0.2324, n=10, wins 80%)
- slo rr_g - rr @rho=0.8: +0.041 +/- 0.038 (p=0.0273, n=10, wins 90%)
- slo rr_g - rr @rho=0.9: +0.055 +/- 0.034 (p=0.0059, n=10, wins 90%)
- slo rr_g - rr @rho=1.0: +0.076 +/- 0.043 (p=0.0059, n=10, wins 90%)
- rho sweep, per policy (cslo / bcslo / viol / cgoodput):
  rho=0.4: local 0.422/0.410/0.166/417; rr 0.815/0.779/0.179/800; rr_g 0.815/0.795/0.178/799; epara 0.823/0.813/0.177/807; epara_priv 0.986/0.978/0.000/967; tera 0.987/0.985/0.000/968; ours 0.983/0.976/0.000/964
  rho=0.6: local 0.291/0.296/0.166/432; rr 0.767/0.754/0.191/1127; rr_g 0.768/0.747/0.194/1130; epara 0.810/0.814/0.188/1191; epara_priv 0.961/0.957/0.000/1413; tera 0.965/0.965/0.000/1420; ours 0.965/0.953/0.000/1419
  rho=0.8: local 0.206/0.211/0.166/407; rr 0.550/0.561/0.195/1078; rr_g 0.574/0.582/0.203/1123; epara 0.708/0.694/0.200/1391; epara_priv 0.841/0.812/0.000/1648; tera 0.867/0.841/0.000/1698; ours 0.812/0.808/0.000/1590
  rho=0.9: local 0.177/0.185/0.166/393; rr 0.340/0.393/0.201/756; rr_g 0.384/0.410/0.202/853; epara 0.349/0.418/0.200/783; epara_priv 0.465/0.545/0.000/1035; tera 0.469/0.549/0.000/1047; ours 0.434/0.529/0.000/970
  rho=1.0: local 0.152/0.151/0.165/374; rr 0.226/0.280/0.204/557; rr_g 0.284/0.310/0.206/696; epara 0.190/0.275/0.196/470; epara_priv 0.289/0.396/0.000/710; tera 0.273/0.389/0.000/673; ours 0.265/0.379/0.000/653

## C. Privacy strictness (rho=0.8)

- sens=0.0: epara slo 0.883 cslo 0.883 bcslo 0.856 viol 0.000, epara_priv slo 0.883 cslo 0.883 bcslo 0.856 viol 0.000, tera slo 0.847 cslo 0.847 bcslo 0.842 viol 0.000 | TRACE-TF cslo -0.036+/-0.095 p=0.084; bcslo -0.014+/-0.048 p=0.084 | TF-EPARA cslo +0.000 p=nan
- sens=0.2: epara slo 0.883 cslo 0.793 bcslo 0.770 viol 0.103, epara_priv slo 0.864 cslo 0.864 bcslo 0.850 viol 0.000, tera slo 0.847 cslo 0.847 bcslo 0.828 viol 0.000 | TRACE-TF cslo -0.017+/-0.053 p=0.695; bcslo -0.022+/-0.031 p=0.160 | TF-EPARA cslo +0.071 p=0.037
- sens=0.4: epara slo 0.883 cslo 0.703 bcslo 0.691 viol 0.205, epara_priv slo 0.845 cslo 0.845 bcslo 0.818 viol 0.000, tera slo 0.873 cslo 0.873 bcslo 0.833 viol 0.000 | TRACE-TF cslo +0.027+/-0.015 p=0.006; bcslo +0.015+/-0.024 p=0.232 | TF-EPARA cslo +0.142 p=0.002
- sens=0.6: epara slo 0.883 cslo 0.614 bcslo 0.606 viol 0.307, epara_priv slo 0.751 cslo 0.751 bcslo 0.761 viol 0.000, tera slo 0.803 cslo 0.803 bcslo 0.786 viol 0.000 | TRACE-TF cslo +0.051+/-0.024 p=0.002; bcslo +0.025+/-0.032 p=0.105 | TF-EPARA cslo +0.137 p=0.006
- sens=0.8: epara slo 0.883 cslo 0.523 bcslo 0.525 viol 0.411, epara_priv slo 0.572 cslo 0.572 bcslo 0.620 viol 0.000, tera slo 0.595 cslo 0.595 bcslo 0.632 viol 0.000 | TRACE-TF cslo +0.022+/-0.036 p=0.193; bcslo +0.012+/-0.024 p=0.375 | TF-EPARA cslo +0.050 p=0.275

## B. Energy (rho=0.8)

- soft cap x1.0: cslo [epara_priv 0.841, ours 0.812, ours_b 0.808, ours_c 0.841, energy 0.720] thr [epara_priv 0.084, ours 0.022, ours_b 0.030, ours_c 0.078, energy 0.058] 
    ours-TF: -0.028+/-0.040 p=0.232
    ours_b-TF: -0.033+/-0.037 p=0.037
    ours_c-TF: +0.000+/-0.031 p=0.625
- soft cap x0.7: cslo [epara_priv 0.706, ours 0.661, ours_b 0.681, ours_c 0.732, energy 0.533] thr [epara_priv 0.189, ours 0.138, ours_b 0.120, ours_c 0.190, energy 0.167] 
    ours-TF: -0.045+/-0.084 p=0.432
    ours_b-TF: -0.025+/-0.070 p=0.275
    ours_c-TF: +0.025+/-0.049 p=0.432
- soft cap x0.5: cslo [epara_priv 0.518, ours 0.454, ours_b 0.479, ours_c 0.508, energy 0.304] thr [epara_priv 0.222, ours 0.200, ours_b 0.218, ours_c 0.237, energy 0.171] 
    ours-TF: -0.064+/-0.069 p=0.105
    ours_b-TF: -0.040+/-0.062 p=0.275
    ours_c-TF: -0.011+/-0.059 p=1.000
- soft cap x0.35: cslo [epara_priv 0.419, ours 0.319, ours_b 0.364, ours_c 0.399, energy 0.218] thr [epara_priv 0.269, ours 0.214, ours_b 0.239, ours_c 0.276, energy 0.169] 
    ours-TF: -0.100+/-0.052 p=0.002
    ours_b-TF: -0.056+/-0.051 p=0.049
    ours_c-TF: -0.020+/-0.052 p=0.432
- outage cap x1.0: cslo [epara_priv 0.818, ours 0.798, ours_b 0.804, ours_c 0.776, energy 0.650] thr [epara_priv 0.005, ours 0.002, ours_b 0.003, ours_c 0.004, energy 0.004] avail [epara_priv 0.88, ours 0.90, ours_b 0.90, ours_c 0.87, energy 0.87]
    ours-TF: -0.020+/-0.046 p=0.625
    ours_b-TF: -0.013+/-0.041 p=0.695
    ours_c-TF: -0.041+/-0.051 p=0.131
- outage cap x0.7: cslo [epara_priv 0.709, ours 0.526, ours_b 0.609, ours_c 0.436, energy 0.347] thr [epara_priv 0.014, ours 0.009, ours_b 0.011, ours_c 0.010, energy 0.008] avail [epara_priv 0.68, ours 0.65, ours_b 0.65, ours_c 0.61, energy 0.61]
    ours-TF: -0.182+/-0.056 p=0.002
    ours_b-TF: -0.100+/-0.045 p=0.002
    ours_c-TF: -0.273+/-0.045 p=0.002
- outage cap x0.5: cslo [epara_priv 0.568, ours 0.334, ours_b 0.425, ours_c 0.285, energy 0.234] thr [epara_priv 0.022, ours 0.010, ours_b 0.015, ours_c 0.006, energy 0.009] avail [epara_priv 0.47, ours 0.40, ours_b 0.39, ours_c 0.36, energy 0.38]
    ours-TF: -0.233+/-0.037 p=0.002
    ours_b-TF: -0.142+/-0.027 p=0.002
    ours_c-TF: -0.283+/-0.044 p=0.002
- outage cap x0.35: cslo [epara_priv 0.434, ours 0.236, ours_b 0.313, ours_c 0.206, energy 0.167] thr [epara_priv 0.019, ours 0.007, ours_b 0.013, ours_c 0.004, energy 0.006] avail [epara_priv 0.31, ours 0.21, ours_b 0.22, ours_c 0.21, energy 0.19]
    ours-TF: -0.198+/-0.024 p=0.002
    ours_b-TF: -0.120+/-0.025 p=0.002
    ours_c-TF: -0.227+/-0.029 p=0.002

## D. Energy ablation (cap x0.5, rho=0.8)

- beta=0.0, theta=0.0: soft cslo 0.518, outage cslo 0.568, avail 0.47
- beta=0.0, theta=0.25: soft cslo 0.546, outage cslo 0.556, avail 0.47
- beta=0.5, theta=0.0: soft cslo 0.513, outage cslo 0.438, avail 0.38
- beta=1.0, theta=0.0: soft cslo 0.469, outage cslo 0.334, avail 0.39
- beta=1.0, theta=0.25: soft cslo 0.454, outage cslo 0.334, avail 0.40
- beta=1.0, theta=0.4: soft cslo 0.463, outage cslo 0.346, avail 0.39
- beta=2.0, theta=0.25: soft cslo 0.409, outage cslo 0.317, avail 0.37

## D2. Best-fit clearance gamma (60% sensitive)

- gamma=1.0: cslo 0.751+/-0.049, bcslo 0.761+/-0.051
  gamma=0.5 vs 1.0 paired cslo diff +0.039+/-0.032 p=0.027
- gamma=0.5: cslo 0.790+/-0.057, bcslo 0.775+/-0.042
  gamma=0.3 vs 1.0 paired cslo diff +0.051+/-0.024 p=0.002
- gamma=0.3: cslo 0.803+/-0.045, bcslo 0.786+/-0.040
  gamma=0.1 vs 1.0 paired cslo diff +0.055+/-0.024 p=0.002
- gamma=0.1: cslo 0.806+/-0.055, bcslo 0.789+/-0.045

## E. Sync staleness

- rho=0.8 H=0.1: rr slo 0.678 hops 1.25, epara slo 0.901 hops 0.74, epara_priv slo 0.842 hops 0.77
- rho=0.8 H=0.25: rr slo 0.678 hops 1.25, epara slo 0.888 hops 0.71, epara_priv slo 0.852 hops 0.78
- rho=0.8 H=0.5: rr slo 0.678 hops 1.25, epara slo 0.919 hops 0.74, epara_priv slo 0.858 hops 0.79
- rho=0.8 H=1.0: rr slo 0.678 hops 1.25, epara slo 0.883 hops 0.80, epara_priv slo 0.841 hops 0.83
- rho=0.8 H=2.0: rr slo 0.678 hops 1.25, epara slo 0.862 hops 0.88, epara_priv slo 0.781 hops 0.90
- rho=1.0 H=0.1: rr slo 0.281 hops 1.73, epara slo 0.180 hops 0.66, epara_priv slo 0.176 hops 0.80
- rho=1.0 H=0.25: rr slo 0.281 hops 1.73, epara slo 0.183 hops 0.80, epara_priv slo 0.186 hops 0.88
- rho=1.0 H=0.5: rr slo 0.281 hops 1.73, epara slo 0.211 hops 0.92, epara_priv slo 0.229 hops 1.01
- rho=1.0 H=1.0: rr slo 0.281 hops 1.73, epara slo 0.236 hops 1.03, epara_priv slo 0.289 hops 1.08
- rho=1.0 H=2.0: rr slo 0.281 hops 1.73, epara slo 0.263 hops 1.11, epara_priv slo 0.306 hops 1.11

## G. Energy weighting vs sync period (cap x0.5)

- soft H=0.1: TF 0.456, TF+EW-TF -0.096+/-0.067 p=0.014; TF+EC-TF +0.013+/-0.118 p=0.625
- soft H=0.25: TF 0.453, TF+EW-TF -0.091+/-0.087 p=0.049; TF+EC-TF -0.001+/-0.086 p=0.770
- soft H=0.5: TF 0.485, TF+EW-TF -0.085+/-0.075 p=0.049; TF+EC-TF -0.035+/-0.090 p=0.492
- soft H=1.0: TF 0.518, TF+EW-TF -0.064+/-0.069 p=0.105; TF+EC-TF -0.011+/-0.059 p=1.000
- soft H=2.0: TF 0.547, TF+EW-TF -0.079+/-0.030 p=0.002; TF+EC-TF -0.026+/-0.049 p=0.160
- outage H=0.1: TF 0.616, TF+EW-TF -0.388+/-0.036 p=0.002; TF+EC-TF -0.443+/-0.042 p=0.002
- outage H=0.25: TF 0.596, TF+EW-TF -0.337+/-0.050 p=0.002; TF+EC-TF -0.419+/-0.028 p=0.002
- outage H=0.5: TF 0.590, TF+EW-TF -0.301+/-0.038 p=0.002; TF+EC-TF -0.380+/-0.042 p=0.002
- outage H=1.0: TF 0.568, TF+EW-TF -0.233+/-0.037 p=0.002; TF+EC-TF -0.283+/-0.044 p=0.002
- outage H=2.0: TF 0.541, TF+EW-TF -0.170+/-0.023 p=0.002; TF+EC-TF -0.183+/-0.028 p=0.002

## F. Scale

- N=10: rr cslo 0.618 dec 1.4us, epara_priv cslo 0.823 dec 18.0us, tera cslo 0.854 dec 20.1us
- N=30: rr cslo 0.581 dec 1.6us, epara_priv cslo 0.855 dec 29.7us, tera cslo 0.856 dec 32.8us
- N=60: rr cslo 0.601 dec 1.3us, epara_priv cslo 0.908 dec 35.6us, tera cslo 0.935 dec 37.0us
- N=120: rr cslo 0.569 dec 1.2us, epara_priv cslo 0.883 dec 51.9us, tera cslo 0.933 dec 51.2us
