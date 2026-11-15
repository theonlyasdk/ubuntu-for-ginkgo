path = "/root/ginkgo/linux/sound/soc/qcom/sm8250.c"
with open(path, "r") as f:
    c = f.read()

# 1. Update PRIMARY_MI2S_RX in startup
old_startup_pri = """\tcase PRIMARY_MI2S_RX:
\t\tcodec_dai_fmt |= SND_SOC_DAIFMT_NB_NF | SND_SOC_DAIFMT_I2S;
\t\tsnd_soc_dai_set_sysclk(cpu_dai,
\t\t\tQ6AFE_LPASS_CLK_ID_PRI_MI2S_IBIT,
\t\t\tMI2S_BCLK_RATE, SNDRV_PCM_STREAM_PLAYBACK);
\t\tsnd_soc_dai_set_fmt(cpu_dai, fmt);
\t\tsnd_soc_dai_set_fmt(codec_dai, codec_dai_fmt);
\t\tbreak;"""

new_startup_pri = """\tcase PRIMARY_MI2S_RX:
\t\tcodec_dai_fmt |= SND_SOC_DAIFMT_NB_NF | SND_SOC_DAIFMT_I2S;
\t\tsnd_soc_dai_set_sysclk(cpu_dai,
\t\t\tQ6AFE_LPASS_CLK_ID_MCLK_1,
\t\t\t19200000, SNDRV_PCM_STREAM_PLAYBACK);
\t\tsnd_soc_dai_set_sysclk(cpu_dai,
\t\t\tQ6AFE_LPASS_CLK_ID_PRI_MI2S_IBIT,
\t\t\tMI2S_BCLK_RATE, SNDRV_PCM_STREAM_PLAYBACK);
\t\tsnd_soc_dai_set_fmt(cpu_dai, fmt);
\t\tsnd_soc_dai_set_fmt(codec_dai, codec_dai_fmt);
\t\tbreak;"""

assert old_startup_pri in c, "old_startup_pri not found"
c = c.replace(old_startup_pri, new_startup_pri, 1)

# 2. Add sm8250_snd_shutdown
shutdown_func = """static void sm8250_snd_shutdown(struct snd_pcm_substream *substream)
{
\tstruct snd_soc_pcm_runtime *rtd = snd_soc_substream_to_rtd(substream);
\tstruct snd_soc_dai *cpu_dai = snd_soc_rtd_to_cpu(rtd, 0);

\tswitch (cpu_dai->id) {
\tcase PRIMARY_MI2S_RX:
\t\tsnd_soc_dai_set_sysclk(cpu_dai,
\t\t\tQ6AFE_LPASS_CLK_ID_MCLK_1,
\t\t\t0, SNDRV_PCM_STREAM_PLAYBACK);
\t\tsnd_soc_dai_set_sysclk(cpu_dai,
\t\t\tQ6AFE_LPASS_CLK_ID_PRI_MI2S_IBIT,
\t\t\t0, SNDRV_PCM_STREAM_PLAYBACK);
\t\tbreak;
\tdefault:
\t\tbreak;
\t}

\tqcom_snd_sdw_shutdown(substream);
}

static const struct snd_soc_ops sm8250_be_ops = {
\t.startup = sm8250_snd_startup,
\t.shutdown = sm8250_snd_shutdown,"""

old_ops = """static const struct snd_soc_ops sm8250_be_ops = {
\t.startup = sm8250_snd_startup,
\t.shutdown = qcom_snd_sdw_shutdown,"""

assert old_ops in c, "old_ops not found"
c = c.replace(old_ops, shutdown_func, 1)

with open(path, "w") as f:
    f.write(c)

print("Patched sm8250.c successfully!")
