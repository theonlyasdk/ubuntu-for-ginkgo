import sys

# 1. Update nt36xxx.h
h_path = '/root/ginkgo/linux/drivers/input/touchscreen/nt36xxx/nt36xxx.h'
with open(h_path, 'r') as f:
    h = f.read()

old_fb_h = """#if defined(CONFIG_FB)
\tstruct workqueue_struct *workqueue;
\tstruct work_struct resume_work;
#ifdef _MSM_DRM_NOTIFY_H_
\tstruct notifier_block drm_notif;
#else
\tstruct notifier_block fb_notif;
#endif
#elif defined(CONFIG_HAS_EARLYSUSPEND)
\tstruct early_suspend early_suspend;
#endif"""

new_wq_h = """\tstruct workqueue_struct *workqueue;
\tstruct work_struct resume_work;"""

assert old_fb_h in h, 'old_fb_h not found in nt36xxx.h'
h = h.replace(old_fb_h, new_wq_h)

with open(h_path, 'w') as f:
    f.write(h)
print('nt36xxx.h patched successfully')

# 2. Update nt36xxx.c
c_path = '/root/ginkgo/linux/drivers/input/touchscreen/nt36xxx/nt36xxx.c'
with open(c_path, 'r') as f:
    c = f.read()

# Remove old CONFIG_FB header block
old_top = """/*
 * ginkgo port: mainline has no FB_EARLY_EVENT_BLANK / msm_drm_notify /
 * earlysuspend. nt36xxx.h already undefines CONFIG_FB for every
 * translation unit, but that happens when the header is included - which is
 * AFTER this block - so CONFIG_FB was still live here and the downstream
 * <linux/msm_drm_notify.h> (nonexistent in mainline) got pulled in.
 * Undefine it up front so the FB block and all FB code compile out.
 */
#undef CONFIG_FB

#if defined(CONFIG_FB)
#ifdef CONFIG_DRM_MSM
#include <linux/msm_drm_notify.h>
#endif
#include <linux/notifier.h>
#include <linux/fb.h>
#elif defined(CONFIG_HAS_EARLYSUSPEND)
#include <linux/earlysuspend.h>
#endif"""

new_top = """/*
 * ginkgo port: Panel enable/disable notification manages touch sleep and resume.
 */"""

assert old_top in c, 'old_top not found in nt36xxx.c'
c = c.replace(old_top, new_top)

# Replace forward declarations with panel notification handlers & touch_wake sysfs
old_fwd = """#if defined(CONFIG_FB)
static void nvt_ts_resume_work(struct work_struct *work);
#ifdef _MSM_DRM_NOTIFY_H_
static int nvt_drm_notifier_callback(struct notifier_block *self, unsigned long event, void *data);
#else
static int nvt_fb_notifier_callback(struct notifier_block *self, unsigned long event, void *data);
#endif
#elif defined(CONFIG_HAS_EARLYSUSPEND)
static void nvt_ts_early_suspend(struct early_suspend *h);
static void nvt_ts_late_resume(struct early_suspend *h);
#endif"""

new_fwd = """static uint8_t bTouchIsAwake;
static void nvt_ts_resume_work(struct work_struct *work);
static int32_t nvt_ts_resume(struct device *dev);
static int32_t nvt_ts_suspend(struct device *dev);

static void nvt_ts_resume_work(struct work_struct *work)
{
\tstruct nvt_ts_data *ts_data =
\t\tcontainer_of(work, struct nvt_ts_data, resume_work);

\tNVT_LOG("resume_work executing\\n");
\tnvt_ts_resume(&ts_data->client->dev);
}

void nvt_ts_panel_resume(void)
{
\tNVT_LOG("panel resume notification received (awake=%d, ready=%d)\\n",
\t\tbTouchIsAwake, driver_ready);
\tif (ts && driver_ready && ts->workqueue) {
\t\tqueue_work(ts->workqueue, &ts->resume_work);
\t}
}
EXPORT_SYMBOL(nvt_ts_panel_resume);

void nvt_ts_panel_suspend(void)
{
\tNVT_LOG("panel suspend notification received (awake=%d, ready=%d)\\n",
\t\tbTouchIsAwake, driver_ready);
\tif (ts && driver_ready) {
\t\tif (ts->workqueue)
\t\t\tcancel_work_sync(&ts->resume_work);
\t\tnvt_ts_suspend(&ts->client->dev);
\t}
}
EXPORT_SYMBOL(nvt_ts_panel_suspend);

static ssize_t touch_wake_show(struct device *dev,
\t\t\t       struct device_attribute *attr, char *buf)
{
\treturn sysfs_emit(buf, "%d\\n", bTouchIsAwake);
}

static ssize_t touch_wake_store(struct device *dev,
\t\t\t\tstruct device_attribute *attr,
\t\t\t\tconst char *buf, size_t count)
{
\tbool wake;
\tint ret;

\tret = kstrtobool(buf, &wake);
\tif (ret)
\t\treturn ret;

\tif (wake) {
\t\tNVT_LOG("manual touch_wake -> resume\\n");
\t\tnvt_ts_resume(dev);
\t} else {
\t\tNVT_LOG("manual touch_wake -> suspend\\n");
\t\tnvt_ts_suspend(dev);
\t}

\treturn count;
}
static DEVICE_ATTR_RW(touch_wake);"""

assert old_fwd in c, 'old_fwd not found in nt36xxx.c'
c = c.replace(old_fwd, new_fwd)

# Remove duplicate bTouchIsAwake definition
c = c.replace('\nstatic uint8_t bTouchIsAwake = 0;\n', '\n/* original bTouchIsAwake */\n', 1)

# Replace probe registration block
old_probe_reg = """#if defined(CONFIG_FB)
\tts->workqueue = create_singlethread_workqueue("nvt_ts_workqueue");
\tif (!ts->workqueue) {
\t\tNVT_ERR("create nvt_ts_workqueue fail");
\t\tret = -ENOMEM;
\t\tgoto err_create_nvt_ts_workqueue_failed;
\t}
\tINIT_WORK(&ts->resume_work, nvt_ts_resume_work);
#ifdef _MSM_DRM_NOTIFY_H_
\tts->drm_notif.notifier_call = nvt_drm_notifier_callback;
\tret = msm_drm_register_client(&ts->drm_notif);
\tif(ret) {
\t\tNVT_ERR("register drm_notifier failed. ret=%d\\n", ret);
\t\tgoto err_register_drm_notif_failed;
\t}
#else
\tts->fb_notif.notifier_call = nvt_fb_notifier_callback;
\tret = fb_register_client(&ts->fb_notif);
\tif(ret) {
\t\tNVT_ERR("register fb_notifier failed. ret=%d\\n", ret);
\t\tgoto err_register_fb_notif_failed;
\t}
#endif
#elif defined(CONFIG_HAS_EARLYSUSPEND)
\tts->early_suspend.level = EARLY_SUSPEND_LEVEL_BLANK_SCREEN + 1;
\tts->early_suspend.suspend = nvt_ts_early_suspend;
\tts->early_suspend.resume = nvt_ts_late_resume;
\tret = register_early_suspend(&ts->early_suspend);
\tif(ret) {
\t\tNVT_ERR("register early suspend failed. ret=%d\\n", ret);
\t\tgoto err_register_early_suspend_failed;
\t}
#endif"""

new_probe_reg = """\tts->workqueue = create_singlethread_workqueue("nvt_ts_workqueue");
\tif (!ts->workqueue) {
\t\tNVT_ERR("create nvt_ts_workqueue fail\\n");
\t\tret = -ENOMEM;
\t\tgoto err_create_nvt_ts_workqueue_failed;
\t}
\tINIT_WORK(&ts->resume_work, nvt_ts_resume_work);

\tret = device_create_file(&client->dev, &dev_attr_touch_wake);
\tif (ret)
\t\tNVT_ERR("failed to create touch_wake sysfs attr: %d\\n", ret);"""

assert old_probe_reg in c, 'old_probe_reg not found in nt36xxx.c'
c = c.replace(old_probe_reg, new_probe_reg)

# Replace probe error handling block
old_probe_err = """#if defined(CONFIG_FB)
err_create_nvt_ts_workqueue_failed:
\tif (ts->workqueue)
\t\tdestroy_workqueue(ts->workqueue);
#ifdef _MSM_DRM_NOTIFY_H_
\tif (msm_drm_unregister_client(&ts->drm_notif))
\t\tNVT_ERR("Error occurred while unregistering drm_notifier.\\n");
err_register_drm_notif_failed:
#else
\tif (fb_unregister_client(&ts->fb_notif))
\t\tNVT_ERR("Error occurred while unregistering fb_notifier.\\n");
err_register_fb_notif_failed:
#endif
#elif defined(CONFIG_HAS_EARLYSUSPEND)
\tunregister_early_suspend(&ts->early_suspend);
err_register_early_suspend_failed:
#endif"""

new_probe_err = """err_create_nvt_ts_workqueue_failed:
\treturn ret;"""

assert old_probe_err in c, 'old_probe_err not found in nt36xxx.c'
c = c.replace(old_probe_err, new_probe_err)

# Remove old notifier callbacks block
old_callbacks = """#if defined(CONFIG_FB)
static void nvt_ts_resume_work(struct work_struct *work)
{
\tnvt_ts_resume(&ts->client->dev);
}
#ifdef _MSM_DRM_NOTIFY_H_
static int nvt_drm_notifier_callback(struct notifier_block *self, unsigned long event, void *data)
{
\tstruct msm_drm_notifier *evdata = data;
\tint *blank;
\tstruct nvt_ts_data *ts =
\t\tcontainer_of(self, struct nvt_ts_data, drm_notif);

\tif (!evdata || (evdata->id != 0))
\t\treturn 0;

\tif (evdata->data && ts) {
\t\tblank = evdata->data;
\t\tif (event == MSM_DRM_EARLY_EVENT_BLANK) {
\t\t\tif (*blank == MSM_DRM_BLANK_POWERDOWN) {
\t\t\t\tNVT_LOG("event=%lu, *blank=%d\\n", event, *blank);
\t\t\t\tcancel_work_sync(&ts->resume_work);
\t\t\t\tnvt_ts_suspend(&ts->client->dev);
\t\t\t}
\t\t} else if (event == MSM_DRM_EVENT_BLANK) {
\t\t\tif (*blank == MSM_DRM_BLANK_UNBLANK) {
\t\t\t\tNVT_LOG("event=%lu, *blank=%d\\n", event, *blank);
\t\t\t\t//nvt_ts_resume(&ts->client->dev);
\t\t\t\tqueue_work(ts->workqueue, &ts->resume_work);
\t\t\t}
\t\t}
\t}

\treturn 0;
}
#else
static int nvt_fb_notifier_callback(struct notifier_block *self, unsigned long event, void *data)
{
\tstruct fb_event *evdata = data;
\tint *blank;
\tstruct nvt_ts_data *ts =
\t\tcontainer_of(self, struct nvt_ts_data, fb_notif);

\tif (evdata && evdata->data && event == FB_EARLY_EVENT_BLANK) {
\t\tblank = evdata->data;
\t\tif (*blank == FB_BLANK_POWERDOWN) {
\t\t\tNVT_LOG("event=%lu, *blank=%d\\n", event, *blank);
\t\t\tnvt_ts_suspend(&ts->client->dev);
\t\t}
\t} else if (evdata && evdata->data && event == FB_EVENT_BLANK) {
\t\tblank = evdata->data;
\t\tif (*blank == FB_BLANK_UNBLANK) {
\t\t\tNVT_LOG("event=%lu, *blank=%d\\n", event, *blank);
\t\t\tnvt_ts_resume(&ts->client->dev);
\t\t}
\t}

\treturn 0;
}
#endif
#elif defined(CONFIG_HAS_EARLYSUSPEND)
/*******************************************************
Description:
\tNovatek touchscreen driver early suspend function.

return:
\tn.a.
*******************************************************/
static void nvt_ts_early_suspend(struct early_suspend *h)
{
\tnvt_ts_suspend(ts->client, PMSG_SUSPEND);
}

/*******************************************************
Description:
\tNovatek touchscreen driver late resume function.

return:
\tn.a.
*******************************************************/
static void nvt_ts_late_resume(struct early_suspend *h)
{
\tnvt_ts_resume(ts->client);
}
#endif"""

new_callbacks = """/* callbacks handled via nvt_ts_panel_resume / suspend */"""

assert old_callbacks in c, 'old_callbacks not found in nt36xxx.c'
c = c.replace(old_callbacks, new_callbacks)

with open(c_path, 'w') as f:
    f.write(c)
print('nt36xxx.c patched successfully')

# 3. Update panel-novatek-nt36672a.c
p_path = '/root/ginkgo/linux/drivers/gpu/drm/panel/panel-novatek-nt36672a.c'
with open(p_path, 'r') as f:
    p = f.read()

# Add weak declarations
weak_decl = """void __weak nvt_ts_panel_resume(void) {}
void __weak nvt_ts_panel_suspend(void) {}

static inline struct nt36672a_panel *to_nt36672a_panel"""

assert 'static inline struct nt36672a_panel *to_nt36672a_panel' in p, 'to_nt36672a_panel not found'
p = p.replace('static inline struct nt36672a_panel *to_nt36672a_panel', weak_decl, 1)

# In nt36672a_panel_enable (fast path when pinfo->inited)
old_fast_resume = """\tif (pinfo->inited) {
\t\terr = mipi_dsi_dcs_set_display_on(pinfo->link);
\t\tif (err < 0)
\t\t\tdev_err(panel->dev, "resume 0x29 failed: %d\\n", err);
\t\tmsleep(20);
\t\tpinfo->asleep = false;
\t\treturn err;
\t}"""

new_fast_resume = """\tif (pinfo->inited) {
\t\terr = mipi_dsi_dcs_set_display_on(pinfo->link);
\t\tif (err < 0)
\t\t\tdev_err(panel->dev, "resume 0x29 failed: %d\\n", err);
\t\tmsleep(20);
\t\tpinfo->asleep = false;
\t\tnvt_ts_panel_resume();
\t\treturn err;
\t}"""

assert old_fast_resume in p, 'old_fast_resume not found'
p = p.replace(old_fast_resume, new_fast_resume)

# In nt36672a_panel_enable (initial init path)
old_init_done = """\tdev_info(panel->dev, "panel init complete\\n");

\tmsleep(120);
\tpinfo->inited = true;
\tpinfo->asleep = false;

\treturn 0;"""

new_init_done = """\tdev_info(panel->dev, "panel init complete\\n");

\tmsleep(120);
\tpinfo->inited = true;
\tpinfo->asleep = false;
\tnvt_ts_panel_resume();

\treturn 0;"""

assert old_init_done in p, 'old_init_done not found'
p = p.replace(old_init_done, new_init_done)

# In nt36672a_panel_disable
old_disable = """static int nt36672a_panel_disable(struct drm_panel *panel)
{
\tstruct nt36672a_panel *pinfo = to_nt36672a_panel(panel);
\tint err;

\terr = mipi_dsi_dcs_set_display_off(pinfo->link);"""

new_disable = """static int nt36672a_panel_disable(struct drm_panel *panel)
{
\tstruct nt36672a_panel *pinfo = to_nt36672a_panel(panel);
\tint err;

\tnvt_ts_panel_suspend();

\terr = mipi_dsi_dcs_set_display_off(pinfo->link);"""

assert old_disable in p, 'old_disable not found'
p = p.replace(old_disable, new_disable)

with open(p_path, 'w') as f:
    f.write(p)
print('panel-novatek-nt36672a.c patched successfully')
