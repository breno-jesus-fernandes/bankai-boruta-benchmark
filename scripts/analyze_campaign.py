"""Reproduce quality/scaling tables, paired comparisons and publication figures."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from bankai_benchmark.aggregate_latex import aggregate, distribution, validated_results, write_csv
from bankai_benchmark.config import COMPETITORS, SEEDS, atomic_json
from scaling48 import compare

DATASETS=('industrial','credito','bioinformatica','ciberseguranca')
TITLES=('Industrial','Credit','Bioinformatics','Cybersecurity')
LABELS=('Classic native','Classic adapter','Greedy native','BorutaPy–LGBM',
        'BorutaPy–ET','Python Greedy–Bankai','Python Greedy–LGBM')
SHORT=('C/R','C/A','G/R','BP-LGBM','BP-ET','GB-Bankai','GB-LGBM')
COLORS=('#0072B2','#56B4E9','#009E73','#E69F00','#CC79A7','#006D4A','#D55E00')


def paired_comparisons(rows):
    out=[]
    lookup={(r['dataset'],r['competitor'],r['seed']):r for r in rows}
    pairs=[('bankai_classic_native','bankai_classic_adapter'),
           ('bankai_classic_native','borutapy_lightgbm_rf'),
           ('bankai_classic_native','borutapy_sklearn_et'),
           ('bankai_greedy_native','greedy_borutapy_bankai')]
    for dataset in DATASETS:
        for a,b in pairs:
            if not all((dataset,method,seed) in lookup for method in (a,b) for seed in SEEDS): continue
            paired=[(lookup[(dataset,a,s)],lookup[(dataset,b,s)]) for s in SEEDS]
            row=dict(dataset=dataset,method_a=a,method_b=b,paired_seeds=len(paired),
                identical_confirmed_sets=sum(x['selected_indices']==y['selected_indices'] for x,y in paired),
                identical_tentative_sets=sum(x['tentative_indices']==y['tentative_indices'] for x,y in paired),
                faster_a_seeds=sum(x['execution_metrics']['fit_seconds']<y['execution_metrics']['fit_seconds'] for x,y in paired))
            values={
                'speedup_a_over_b':[y['execution_metrics']['fit_seconds']/x['execution_metrics']['fit_seconds'] for x,y in paired],
                'fit_reduction_a_pct':[100*(1-x['execution_metrics']['fit_seconds']/y['execution_metrics']['fit_seconds']) for x,y in paired],
                'rss_reduction_a_pct':[100*(1-x['execution_metrics']['peak_rss_gib']/y['execution_metrics']['peak_rss_gib']) for x,y in paired],
                'recall_a_minus_b_pp':[100*(x['selection_metrics']['recall']-y['selection_metrics']['recall']) for x,y in paired],
                'auc_a_minus_b':[x['downstream_metrics']['roc_auc']-y['downstream_metrics']['roc_auc'] for x,y in paired]}
            for label,v in values.items():row.update({f'{label}_{k}':n for k,n in distribution(v).items()})
            out.append(row)
    return out


def export(fig,root,name):
    for extension in ('svg','pdf','png'):
        metadata={'Date':None,'Creator':'Bankai benchmark'} if extension=='svg' else (
            {'CreationDate':None,'ModDate':None,'Creator':'Bankai benchmark'} if extension=='pdf' else {'Software':'Bankai benchmark'})
        fig.savefig(root/f'{name}.{extension}',bbox_inches='tight',dpi=220,metadata=metadata)
        if extension=='svg':
            path=root/f'{name}.{extension}'
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    plt.close(fig)


def figures(quality,scaling,output):
    output.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,
                         'svg.fonttype':'none','svg.hashsalt':'bankai-20261017','pdf.fonttype':42})
    lookup={(r['dataset'],r['competitor']):r for r in quality}
    for metric,label,name in [('fit_seconds','Selector fit time (s)','quality_fit_time'),
                              ('peak_rss_gib','Peak RSS (GiB)','quality_peak_memory')]:
        fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
        for ax,dataset,title in zip(axes.flat,DATASETS,TITLES):
            rows=[lookup[(dataset,c)] for c in COMPETITORS]
            median=np.array([r[metric+'_median'] for r in rows])
            q1=np.array([r[metric+'_q1'] for r in rows]);q3=np.array([r[metric+'_q3'] for r in rows])
            ax.barh(range(7),median,color=COLORS,xerr=[median-q1,q3-median],capsize=3)
            ax.set_yticks(range(7),LABELS);ax.invert_yaxis();ax.set_title(title)
            ax.set_xlabel(label);ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
        fig.suptitle('Full quality suite, 16 threads — median and Q1–Q3; five seeds')
        export(fig,output,name)
    fig,axes=plt.subplots(2,2,figsize=(11,6.5),layout='constrained')
    for ax,metric,title in zip(axes.flat,('precision','recall','f1','downstream_roc_auc'),
                              ('Selection precision','Selection recall','Selection F1','Downstream ROC AUC')):
        matrix=np.array([[lookup[(d,c)][metric+'_median'] for c in COMPETITORS] for d in DATASETS])
        im=ax.imshow(matrix,vmin=0,vmax=1,cmap='viridis',aspect='auto')
        ax.set_xticks(range(7),SHORT,rotation=35,ha='right');ax.set_yticks(range(4),TITLES);ax.set_title(title)
        for i in range(4):
            for j in range(7):ax.text(j,i,format(matrix[i,j],'.4f' if metric=='downstream_roc_auc' else '.2f'),
                                      ha='center',va='center',color='white' if matrix[i,j]<.5 else 'black',fontsize=8)
    fig.colorbar(im,ax=list(axes.flat),shrink=.8,label='Median across five seeds')
    export(fig,output,'quality_selection_and_auc')
    for metric,label,name in [('fit_seconds','Selector fit time (s)','scaling_fit_time'),
                              ('speedup_vs_4','Paired speedup vs 4 threads','scaling_speedup')]:
        fig,axes=plt.subplots(2,4,figsize=(11,5.5),layout='constrained')
        for index,(method,title) in enumerate(zip(COMPETITORS,LABELS)):
            ax=axes.flat[index]
            rows=sorted([r for r in scaling if r['competitor']==method],key=lambda r:r['threads'])
            x=np.array([r['threads'] for r in rows]);y=np.array([r[metric+'_median'] for r in rows])
            ax.plot(x,y,color=COLORS[index],linewidth=1.5)
            for j,r in enumerate(rows):
                ax.errorbar(x[j],y[j],yerr=[[y[j]-r[metric+'_q1']],[r[metric+'_q3']-y[j]]],
                    fmt='o',color=COLORS[index],capsize=3,mfc='white' if x[j]==16 else COLORS[index])
            ax.set_xscale('log',base=2);ax.set_xticks([4,8,16],['4','8','16']);ax.set_title(title)
            ax.set_xlabel('Threads');ax.set_ylabel(label);ax.grid(alpha=.15)
            if metric=='speedup_vs_4':ax.axhline(1,color='grey',linestyle=':',linewidth=.7)
        axes.flat[-1].axis('off')
        axes.flat[-1].text(0,.9,'Five paired seeds per method\nBars: Q1–Q3\nFilled: new 4/8-thread fits\nHollow: reused 16-thread fits\n\nSame Industrial profile and image\nSame c7i.4xlarge host class\nSeparate sequential campaigns',va='top')
        export(fig,output,name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quality',required=True);parser.add_argument('--scaling',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    if any(json.loads(p.read_text()).get("protocol") == "paper-v2-a5-amd16" for p in Path(args.quality).rglob("manifest.json")):
        from bankai_benchmark.reporting_v2 import report
        report(args.quality, args.scaling, out)
        return
    global COMPETITORS
    from bankai_benchmark.config import HISTORICAL_COMPETITORS
    COMPETITORS = HISTORICAL_COMPETITORS
    rows,expected,issues=validated_results(args.quality)
    if len(rows)!=140 or issues or any(r['status']!='success' for r in rows):
        raise ValueError('Complete successful 140-trial quality suite required')
    aggregate(args.quality,out/'quality')
    if not compare(args.quality,args.scaling,out/'scaling'):
        raise ValueError('Complete 70-trial scaling suite required')
    pairs=paired_comparisons(rows);write_csv(out/'paired_quality_comparisons.csv',pairs)
    new,_,_=validated_results(args.scaling)
    measured=rows+new
    if len({(r['experiment_id'],r['dataset'],r['competitor'],r['seed'],r['threads']) for r in measured})!=210:
        raise ValueError('Measured trials overlap')
    if any(len(r['provenance']['affinity'])!=r['threads'] for r in measured):
        raise ValueError('Requested CPU affinity was not applied')
    expected_paths={'bankai_classic_native':'rust','bankai_greedy_native':'rust','bankai_classic_adapter':'python'}
    if any(r['diagnostics'].get('path')!=expected_paths[r['competitor']]
           for r in measured if r['competitor'] in expected_paths):
        raise ValueError('Unexpected Bankai execution path')
    pid_count=len({(r['provenance']['task_arn'],r['provenance']['pid']) for r in measured})
    if pid_count!=210:raise ValueError('Repeated worker PID within a task; investigate process isolation')
    thread_lookup={(r['competitor'],r['seed'],r['threads']):r for r in new + [r for r in rows if r['dataset']=='industrial']}
    thread_pairs=[]
    for method in COMPETITORS:
        paired=[(thread_lookup[(method,s,8)],thread_lookup[(method,s,16)]) for s in SEEDS]
        record=dict(competitor=method,paired_seeds=5,
            faster_8_seeds=sum(a['execution_metrics']['fit_seconds']<b['execution_metrics']['fit_seconds'] for a,b in paired),
            identical_confirmed_sets=sum(a['selected_indices']==b['selected_indices'] for a,b in paired))
        for name,values in {
            'fit_reduction_8_vs_16_pct':[100*(1-a['execution_metrics']['fit_seconds']/b['execution_metrics']['fit_seconds']) for a,b in paired],
            'recall_8_minus_16_pp':[100*(a['selection_metrics']['recall']-b['selection_metrics']['recall']) for a,b in paired],
            'auc_8_minus_16':[a['downstream_metrics']['roc_auc']-b['downstream_metrics']['roc_auc'] for a,b in paired]}.items():
            record.update({f'{name}_{k}':v for k,v in distribution(values).items()})
        thread_pairs.append(record)
    write_csv(out/'paired_8_vs_16.csv',thread_pairs)
    def numbers(path):
        parsed=[]
        for row in csv.DictReader(path.open()):
            for key,value in row.items():
                if key.endswith(('_median','_q1','_q3','_iqr')):row[key]=float(value) if value else None
            row['threads']=int(row['threads']);parsed.append(row)
        return parsed
    quality=numbers(out/'quality/summary_by_dataset.csv');scaling=numbers(out/'scaling/thread_scaling.csv')
    figures(quality,scaling,out/'figures')
    for path in out.rglob('*.csv'):
        path.write_text(path.read_text())  # Normalize generated CSVs to LF for source control.
    checks=dict(unique_measured_trials=210,quality=140,new_scaling=70,reused_scaling=35,
        quality_seeds_per_cell=5,scaling_seeds_per_cell=5,scaling_baseline_threads=4,
        observed_distinct_task_pid_pairs=pid_count,affinity_contract_passed=True,bankai_execution_paths_passed=True,
        native_adapter_confirmed_parity={r['dataset']:r['identical_confirmed_sets'] for r in pairs
            if r['method_a']=='bankai_classic_native' and r['method_b']=='bankai_classic_adapter'},
        statistical_scope='Descriptive seed-paired comparisons; quartiles are not confidence intervals; no significance claim.')
    atomic_json(out/'validation.json',checks)
    native_pairs=[r for r in pairs if r['method_a']=='bankai_classic_native' and r['method_b']=='bankai_classic_adapter']
    reductions=[r['fit_reduction_a_pct_median'] for r in native_pairs]
    memory=[r['rss_reduction_a_pct_median'] for r in native_pairs]
    text=['# Resultados consolidados', '',
        '210 medições únicas: 140 de qualidade e 70 novas de escala. Na escala, 35 observações de qualidade a 16 threads são reutilizadas, sem contá-las novamente como execuções.', '',
        '## Principais observações', '',
        '- Bankai Classic nativo apresentou o menor tempo mediano entre as sete configurações em cada um dos quatro perfis de qualidade.',
        f'- Comparado ao adapter, o Classic nativo preservou as seleções confirmadas nos {sum(r["identical_confirmed_sets"] for r in native_pairs)}/20 pares. A redução mediana por seed foi de {min(reductions):.1f}–{max(reductions):.1f}% em tempo e {min(memory):.1f}–{max(memory):.1f}% em pico RSS, dependendo do dataset.',
        '- BorutaPy–ExtraTrees apresentou o menor pico RSS mediano nos quatro datasets. A vantagem de memória do caminho nativo é em relação ao adapter, não uma liderança universal de memória.',
        '- Em Bioinformática, Classic nativo/adapter e BorutaPy–LightGBM encontraram 10/30 features relevantes (recall 0,333) em todos os seeds: os dez sinais correlacionados e nenhuma das vinte features de interação. Os Greedy aumentaram modestamente o recall, junto com falsos positivos.',
        '- Na escala Industrial, os quatro métodos com BankaiRF tiveram menor tempo mediano em 8 threads que em 16. Os dois métodos LightGBM tiveram menor tempo mediano em 16. A diferença de ExtraTrees foi pequena. Isso não estabelece um número de threads ótimo para outros perfis.',
        '- O oracle downstream é uma referência com features verdadeiras; seu desempenho depende do próprio ExtraTrees avaliador e não é o limite ótimo teórico do problema.', '',
        '## Qualidade — 16 threads', '',
        'Medianas de cinco seeds. Quartis/IQR e referências oracle/todas as features estão no CSV.', '',
        '| Dataset | Método | Fit (s) | Pico GiB | Precisão | Recall | AUC |',
        '|---|---|---:|---:|---:|---:|---:|']
    for r in quality:
        text.append(f"| {r['dataset']} | {r['competitor']} | {r['fit_seconds_median']:.2f} | {r['peak_rss_gib_median']:.2f} | {r['precision_median']:.3f} | {r['recall_median']:.3f} | {r['downstream_roc_auc_median']:.4f} |")
    text+=['', '## Classic nativo versus adapter', '',
           'Reduções calculadas em cada seed e depois resumidas pela mediana.', '',
           '| Dataset | Redução do tempo | Redução de pico RSS | Seleções confirmadas idênticas |',
           '|---|---:|---:|---:|']
    for r in pairs:
        if r['method_a']=='bankai_classic_native' and r['method_b']=='bankai_classic_adapter':
            text.append(f"| {r['dataset']} | {r['fit_reduction_a_pct_median']:.1f}% | {r['rss_reduction_a_pct_median']:.1f}% | {r['identical_confirmed_sets']}/5 |")
    text+=['', '## Escala — Industrial', '',
        'Speedup pareado relativo a 4 threads; os dados de 16 threads vêm da qualidade. Nenhuma medição a 1 ou 2 threads foi realizada.', '',
        '| Método | Fit 4 (s) | Fit 8 (s) | Fit 16 (s) | Speedup 8/4 | Speedup 16/4 |',
        '|---|---:|---:|---:|---:|---:|']
    for c in COMPETITORS:
        group={r['threads']:r for r in scaling if r['competitor']==c}
        text.append(f"| {c} | {group[4]['fit_seconds_median']:.2f} | {group[8]['fit_seconds_median']:.2f} | {group[16]['fit_seconds_median']:.2f} | {group[8]['speedup_vs_4_median']:.3f} | {group[16]['speedup_vs_4_median']:.3f} |")
    text+=['', '## Limites de interpretação', '',
        '- Cinco seeds medem variação entre realizações sintéticas; não são cinco repetições do mesmo dataset nem cinco máquinas independentes.',
        '- As medições foram sequenciais. A comparação 8/16 reutiliza uma campanha anterior e não separa completamente efeitos de ordem, host e caches do efeito das threads.',
        '- Mediana e Q1–Q3 descrevem os dados; o IQR não é intervalo de confiança. Não afirmamos significância estatística.',
        '- Os quatro datasets são sintéticos e têm um SNR/perfil fixo cada; os resultados não demonstram generalização para dados reais ou outros perfis.',
        '- Backends diferem em bootstrap, amostragem e splits; a comparação nativo/adapter do mesmo BankaiRF isola melhor o caminho de execução.',
        '- Bioinformática revelou baixo recall das interações: isso é uma limitação observada do perfil testado, não evidência de recuperar todas as features relevantes.',
        '- Eficiência da escala é relativa a quatro threads; sem uma thread não há eficiência paralela convencional.', '',
        '## Artefatos', '',
        '- `quality/`: CSVs, tabelas TeX e placeholders Industrial/16 threads.',
        '- `scaling/`: mediana/IQR, speedups por seed e origem das 35 observações reutilizadas.',
        '- `paired_quality_comparisons.csv`: comparações por seed, paridade da seleção e diferenças de AUC/recall.',
        '- `paired_8_vs_16.csv`: diferenças pareadas entre a campanha nova de 8 threads e os 16 threads reutilizados.',
        '- `figures/`: gráficos SVG/PDF/PNG reproduzíveis, sem gráficos gerados por IA.',
        '- `validation.json`: contagens e paridade confirmadas; não substitui revisão metodológica do artigo.']
    (out/'ANALISE.md').write_text('\n'.join(text)+'\n')


if __name__=='__main__':main()
